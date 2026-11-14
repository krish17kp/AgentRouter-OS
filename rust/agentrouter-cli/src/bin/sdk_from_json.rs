//! JSON compatibility bridge for the synchronous Rust SDK client.

use std::collections::VecDeque;
use std::io::{self, Read};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use agentrouter_cli::sdk::{
    AgentRouterClient, ClientError, SdkRequest, SdkResponse, SdkTransport, SdkTransportError,
    SdkTransportErrorKind,
};
use serde_json::{json, Value};

fn result(value: Result<Value, ClientError>) -> Value {
    match value {
        Ok(value) => json!({"ok": value}),
        Err(ClientError::Api(error)) => json!({
            "error": {
                "status_code": error.status_code,
                "code": error.code,
                "display": error.to_string(),
            }
        }),
        Err(ClientError::Transport(error)) => json!({"transport_error": error.kind.to_string()}),
    }
}

/// In-memory transport for Python/Rust SDK differential tests. It deliberately
/// records only whether the API key header exists, never the key itself.
struct FixtureTransport {
    responses: Mutex<VecDeque<SdkResponse>>,
    requests: Mutex<Vec<Value>>,
    error: Option<SdkTransportErrorKind>,
    base_url: String,
}

impl FixtureTransport {
    fn new(
        fixtures: &[Value],
        error: Option<SdkTransportErrorKind>,
        base_url: &str,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let mut responses = VecDeque::with_capacity(fixtures.len());
        for fixture in fixtures {
            let status_code = fixture
                .get("status_code")
                .and_then(Value::as_u64)
                .and_then(|status| u16::try_from(status).ok())
                .ok_or("fixture status_code must be a u16")?;
            let body = fixture.get("body").ok_or("fixture body is required")?;
            responses.push_back(SdkResponse {
                status_code,
                body: serde_json::to_vec(body)?,
            });
        }
        Ok(Self {
            responses: Mutex::new(responses),
            requests: Mutex::new(Vec::new()),
            error,
            base_url: base_url.trim_end_matches('/').to_owned(),
        })
    }
}

impl SdkTransport for FixtureTransport {
    fn send(&self, request: SdkRequest) -> Result<SdkResponse, SdkTransportError> {
        let body = request
            .body
            .as_deref()
            .and_then(|bytes| serde_json::from_slice::<Value>(bytes).ok());
        let content_type = request
            .headers
            .iter()
            .find(|(name, _)| name.eq_ignore_ascii_case("content-type"))
            .map(|(_, value)| value.clone());
        let api_key_present = request
            .headers
            .iter()
            .any(|(name, _)| name.eq_ignore_ascii_case("x-api-key"));
        self.requests
            .lock()
            .expect("requests mutex poisoned")
            .push(json!({
                "method": request.method,
                // Record only the endpoint suffix. A caller can put credentials
                // in URL userinfo, a query, or a path prefix; none belong in the
                // fixture bridge's stdout.
                "path": request
                    .url
                    .strip_prefix(&self.base_url)
                    .unwrap_or("<unrecognized>"),
                "timeout": {
                    "connect": request.timeout.as_secs_f64(),
                    "read": request.timeout.as_secs_f64(),
                    "write": request.timeout.as_secs_f64(),
                    "pool": request.timeout.as_secs_f64(),
                },
                "body": body,
                "api_key_present": api_key_present,
                "content_type": content_type,
            }));
        if let Some(kind) = self.error {
            return Err(SdkTransportError::new(kind, "fixture failure"));
        }
        self.responses
            .lock()
            .expect("responses mutex poisoned")
            .pop_front()
            .ok_or_else(|| {
                SdkTransportError::new(
                    SdkTransportErrorKind::Other,
                    "fixture has no response remaining",
                )
            })
    }
}

fn fixture_error_kind(name: &str) -> Option<SdkTransportErrorKind> {
    Some(match name {
        "ConnectError" => SdkTransportErrorKind::ConnectError,
        "ConnectTimeout" => SdkTransportErrorKind::ConnectTimeout,
        "ReadError" => SdkTransportErrorKind::ReadError,
        "ReadTimeout" => SdkTransportErrorKind::ReadTimeout,
        "WriteError" => SdkTransportErrorKind::WriteError,
        "WriteTimeout" => SdkTransportErrorKind::WriteTimeout,
        "ProxyError" => SdkTransportErrorKind::ProxyError,
        "RemoteProtocolError" => SdkTransportErrorKind::ProtocolError,
        "InvalidURL" => SdkTransportErrorKind::InvalidUrl,
        "UnsupportedProtocol" => SdkTransportErrorKind::UnsupportedProtocol,
        "TooManyRedirects" => SdkTransportErrorKind::TooManyRedirects,
        "InvalidResponse" => SdkTransportErrorKind::InvalidResponse,
        "ClientClosed" => SdkTransportErrorKind::ClientClosed,
        "TransportError" => SdkTransportErrorKind::Other,
        _ => return None,
    })
}

fn call(client: &AgentRouterClient, operation: &Value) -> Value {
    let name = operation
        .get("name")
        .and_then(Value::as_str)
        .unwrap_or_default();
    match name {
        "health" => result(client.health()),
        "ready" => result(client.ready()),
        "models" => result(client.models().map(Value::Array)),
        "hosts" => result(client.hosts().map(Value::Array)),
        "classify" => {
            let task = operation
                .get("task")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let context_tokens = operation
                .get("context_tokens")
                .and_then(Value::as_number)
                .cloned();
            let risk = operation.get("risk").and_then(Value::as_str);
            let tools = operation
                .get("tools")
                .and_then(Value::as_array)
                .map(|values| {
                    values
                        .iter()
                        .filter_map(Value::as_str)
                        .map(str::to_owned)
                        .collect::<Vec<_>>()
                });
            result(client.classify(task, context_tokens, risk, tools.as_deref()))
        }
        "route" => {
            let task = operation
                .get("task")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let prefer = operation.get("prefer").and_then(Value::as_str);
            let context_tokens = operation
                .get("context_tokens")
                .and_then(Value::as_number)
                .cloned();
            let risk = operation.get("risk").and_then(Value::as_str);
            let tools = operation
                .get("tools")
                .and_then(Value::as_array)
                .map(|values| {
                    values
                        .iter()
                        .filter_map(Value::as_str)
                        .map(str::to_owned)
                        .collect::<Vec<_>>()
                });
            let no_log = operation
                .get("no_log")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            result(client.route(task, prefer, context_tokens, risk, tools.as_deref(), no_log))
        }
        "get_decision" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            result(client.get_decision(id))
        }
        "feedback" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let rating = operation
                .get("rating")
                .and_then(Value::as_i64)
                .unwrap_or_default();
            let note = operation.get("note").and_then(Value::as_str);
            result(client.feedback(id, rating, note))
        }
        "execute_dry_run" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            result(client.execute_dry_run(id))
        }
        _ => json!({"bridge_error": format!("unknown operation '{name}'")}),
    }
}

fn run(request: &Value) -> Result<Value, Box<dyn std::error::Error>> {
    let fixture_mode =
        request.get("mock_responses").is_some() || request.get("mock_transport_error").is_some();
    if fixture_mode
        && std::env::var("AGENTROUTER_TEST_FIXTURE_TRANSPORT")
            .ok()
            .as_deref()
            != Some("1")
    {
        return Err("mock transports are enabled only for explicit test runs".into());
    }
    let base_url = request
        .get("base_url")
        .and_then(Value::as_str)
        .ok_or("base_url must be a string")?;
    let api_key = request.get("api_key").and_then(Value::as_str);
    let timeout_seconds = request
        .get("timeout_seconds")
        .and_then(Value::as_f64)
        .unwrap_or(10.0);
    if !timeout_seconds.is_finite() || timeout_seconds <= 0.0 {
        return Err("timeout_seconds must be finite and positive".into());
    }
    let mock_error = match request.get("mock_transport_error") {
        Some(value) => {
            let name = value
                .as_str()
                .ok_or("mock_transport_error must be a string")?;
            Some(fixture_error_kind(name).ok_or("unknown mock transport error kind")?)
        }
        None => None,
    };
    let mock_responses = request
        .get("mock_responses")
        .map(|value| value.as_array().ok_or("mock_responses must be an array"))
        .transpose()?;
    let fixture_transport = match (mock_responses, mock_error) {
        (Some(fixtures), error) => Some(FixtureTransport::new(fixtures, error, base_url)?),
        (None, Some(error)) => Some(FixtureTransport::new(&[], Some(error), base_url)?),
        (None, None) => None,
    };
    let fixture_transport = fixture_transport.map(Arc::new);
    let client = match &fixture_transport {
        Some(transport) => AgentRouterClient::with_transport_timeout(
            Some(base_url),
            api_key,
            Some(Duration::from_secs_f64(timeout_seconds)),
            transport.clone(),
        ),
        None => AgentRouterClient::new(
            Some(base_url),
            api_key,
            Some(Duration::from_secs_f64(timeout_seconds)),
        ),
    };
    let operations = request
        .get("operations")
        .and_then(Value::as_array)
        .ok_or("operations must be an array")?;
    let results = Value::Array(
        operations
            .iter()
            .map(|operation| call(&client, operation))
            .collect(),
    );
    client.close();
    if let Some(transport) = fixture_transport {
        let requests = transport
            .requests
            .lock()
            .map_err(|_| "fixture request mutex poisoned")?
            .clone();
        Ok(json!({"results": results, "requests": requests}))
    } else {
        Ok(results)
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    println!("{}", serde_json::to_string(&run(&request)?)?);
    Ok(())
}
