//! Synchronous client for the local AgentRouter REST API.
//!
//! Mirrors endpoint payloads and error fields in `agentrouter.sdk`. This
//! client communicates with the local AgentRouter service; it does not execute
//! tools.

use std::time::Duration;

use serde_json::{json, Map, Value};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentRouterError {
    pub status_code: u16,
    pub code: String,
    pub message: String,
}

impl std::fmt::Display for AgentRouterError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[{}] {}: {}", self.status_code, self.code, self.message)
    }
}

impl std::error::Error for AgentRouterError {}

#[derive(Debug)]
pub enum ClientError {
    Api(AgentRouterError),
    Transport(String),
}

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Api(error) => error.fmt(f),
            Self::Transport(error) => f.write_str(error),
        }
    }
}

impl std::error::Error for ClientError {}

/// Remove null fields while retaining explicit false and zero values.
pub fn clean(fields: impl IntoIterator<Item = (String, Value)>) -> Value {
    Value::Object(
        fields
            .into_iter()
            .filter(|(_, value)| !value.is_null())
            .collect::<Map<String, Value>>(),
    )
}

pub struct AgentRouterClient {
    base_url: String,
    api_key: Option<String>,
    agent: ureq::Agent,
}

impl AgentRouterClient {
    pub fn new(base_url: Option<&str>, api_key: Option<&str>, timeout: Option<Duration>) -> Self {
        let base_url = base_url
            .unwrap_or("http://127.0.0.1:8000")
            .trim_end_matches('/');
        let agent = ureq::AgentBuilder::new()
            .redirects(0)
            .timeout(timeout.unwrap_or(Duration::from_secs(10)))
            .build();
        Self {
            base_url: base_url.to_owned(),
            api_key: api_key.filter(|key| !key.is_empty()).map(str::to_owned),
            agent,
        }
    }

    fn request(&self, method: &str, path: &str, body: Option<Value>) -> Result<Value, ClientError> {
        let url = format!("{}{path}", self.base_url);
        let mut request = self.agent.request(method, &url);
        if let Some(api_key) = &self.api_key {
            request = request.set("X-API-Key", api_key);
        }
        let response = match body {
            Some(body) => request
                .set("Content-Type", "application/json")
                .send_string(&body.to_string()),
            None => request.call(),
        };
        match response {
            Ok(response) => {
                let text = response
                    .into_string()
                    .map_err(|error| ClientError::Transport(error.to_string()))?;
                serde_json::from_str(&text)
                    .map_err(|error| ClientError::Transport(error.to_string()))
            }
            Err(ureq::Error::Status(status, response)) => {
                let text = response.into_string().unwrap_or_default();
                let parsed = serde_json::from_str::<Value>(&text).ok();
                let error = parsed
                    .as_ref()
                    .and_then(|value| value.get("error"))
                    .and_then(Value::as_object);
                let code = error
                    .and_then(|value| value.get("code"))
                    .and_then(Value::as_str)
                    .unwrap_or("error")
                    .to_owned();
                let message = error
                    .and_then(|value| value.get("message"))
                    .and_then(Value::as_str)
                    .unwrap_or(&text)
                    .to_owned();
                Err(ClientError::Api(AgentRouterError {
                    status_code: status,
                    code,
                    message,
                }))
            }
            Err(ureq::Error::Transport(error)) => Err(ClientError::Transport(error.to_string())),
        }
    }

    pub fn health(&self) -> Result<Value, ClientError> {
        self.request("GET", "/health", None)
    }

    pub fn ready(&self) -> Result<Value, ClientError> {
        self.request("GET", "/ready", None)
    }

    pub fn models(&self) -> Result<Vec<Value>, ClientError> {
        self.request("GET", "/v1/models", None)?
            .as_array()
            .cloned()
            .ok_or_else(|| ClientError::Transport("expected a JSON array".into()))
    }

    pub fn hosts(&self) -> Result<Vec<Value>, ClientError> {
        self.request("GET", "/v1/hosts", None)?
            .as_array()
            .cloned()
            .ok_or_else(|| ClientError::Transport("expected a JSON array".into()))
    }

    pub fn classify(&self, task: &str, options: Value) -> Result<Value, ClientError> {
        let mut fields = Map::new();
        fields.insert("task".into(), json!(task));
        merge_clean(&mut fields, options);
        self.request("POST", "/v1/classify", Some(Value::Object(fields)))
    }

    pub fn route(&self, task: &str, options: Value) -> Result<Value, ClientError> {
        let mut fields = Map::new();
        fields.insert("task".into(), json!(task));
        merge_clean(&mut fields, options);
        self.request("POST", "/v1/route", Some(Value::Object(fields)))
    }

    pub fn get_decision(&self, decision_id: &str) -> Result<Value, ClientError> {
        self.request("GET", &format!("/v1/decisions/{decision_id}"), None)
    }

    pub fn feedback(
        &self,
        decision_id: &str,
        rating: i64,
        note: Option<&str>,
    ) -> Result<Value, ClientError> {
        self.request(
            "POST",
            "/v1/feedback",
            Some(clean([
                ("decision_id".into(), json!(decision_id)),
                ("rating".into(), json!(rating)),
                (
                    "note".into(),
                    note.map_or(Value::Null, |value| json!(value)),
                ),
            ])),
        )
    }

    pub fn execute_dry_run(&self, decision_id: &str) -> Result<Value, ClientError> {
        self.request(
            "POST",
            "/v1/execute/dry-run",
            Some(json!({"decision_id": decision_id})),
        )
    }
}

fn merge_clean(fields: &mut Map<String, Value>, options: Value) {
    if let Some(options) = options.as_object() {
        fields.extend(
            options
                .iter()
                .filter(|(_, value)| !value.is_null())
                .map(|(key, value)| (key.clone(), value.clone())),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    fn serve_once(status: &str, response: &str) -> (String, thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let response = response.to_owned();
        let status = status.to_owned();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = Vec::new();
            let mut chunk = [0; 2048];
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            loop {
                let size = stream.read(&mut chunk).unwrap();
                if size == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..size]);
                if let Some(head_end) = request
                    .windows(4)
                    .position(|bytes| bytes == b"\r\n\r\n")
                    .map(|position| position + 4)
                {
                    let head = String::from_utf8_lossy(&request[..head_end]);
                    let length = head
                        .lines()
                        .find_map(|line| {
                            line.to_ascii_lowercase()
                                .strip_prefix("content-length: ")
                                .and_then(|value| value.trim().parse::<usize>().ok())
                        })
                        .unwrap_or(0);
                    if request.len() >= head_end + length {
                        break;
                    }
                }
            }
            let text = String::from_utf8_lossy(&request).into_owned();
            write!(
                stream,
                "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .unwrap();
            text
        });
        (format!("http://{address}"), handle)
    }

    #[test]
    fn route_sends_clean_request_and_api_key() {
        let (url, server) = serve_once("200 OK", r#"{"decision_id":"d_1"}"#);
        let client = AgentRouterClient::new(Some(&url), Some("secret"), None);
        let result = client
            .route(
                "write docs",
                json!({"prefer": null, "context_tokens": 0, "no_log": false}),
            )
            .unwrap();
        assert_eq!(result["decision_id"], "d_1");
        let request = server.join().unwrap();
        assert!(request.contains("X-API-Key: secret"));
        let body = request.split("\r\n\r\n").nth(1).unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(body).unwrap(),
            json!({"task": "write docs", "context_tokens": 0, "no_log": false})
        );
    }

    #[test]
    fn non_success_response_preserves_api_error_fields() {
        let (url, server) = serve_once(
            "404 Not Found",
            r#"{"error":{"code":"not_found","message":"missing"}}"#,
        );
        let client = AgentRouterClient::new(Some(&url), None, None);
        let error = client.get_decision("d_missing").unwrap_err();
        assert!(matches!(
            error,
            ClientError::Api(AgentRouterError {
                status_code: 404,
                code,
                message
            }) if code == "not_found" && message == "missing"
        ));
        server.join().unwrap();
    }
}
