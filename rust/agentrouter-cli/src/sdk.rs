//! Synchronous client for the local AgentRouter REST API.
//!
//! Mirrors endpoint payloads and error fields in `agentrouter.sdk`. This
//! client communicates with the local AgentRouter service; it does not execute
//! tools.

use std::io::Read;
use std::sync::{Arc, Condvar, Mutex};
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
    Transport(SdkTransportError),
}

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Api(error) => error.fmt(f),
            Self::Transport(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for ClientError {}

/// Stable transport categories corresponding to the public HTTPX error classes
/// used by the Python SDK. Messages are retained for diagnostics, but callers
/// should branch on the category rather than parsing them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SdkTransportErrorKind {
    ConnectError,
    ConnectTimeout,
    ReadError,
    ReadTimeout,
    WriteError,
    WriteTimeout,
    ProxyError,
    ProtocolError,
    InvalidUrl,
    UnsupportedProtocol,
    TooManyRedirects,
    InvalidResponse,
    ClientClosed,
    Other,
}

impl std::fmt::Display for SdkTransportErrorKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let label = match self {
            Self::ConnectError => "ConnectError",
            Self::ConnectTimeout => "ConnectTimeout",
            Self::ReadError => "ReadError",
            Self::ReadTimeout => "ReadTimeout",
            Self::WriteError => "WriteError",
            Self::WriteTimeout => "WriteTimeout",
            Self::ProxyError => "ProxyError",
            Self::ProtocolError => "RemoteProtocolError",
            Self::InvalidUrl => "InvalidURL",
            Self::UnsupportedProtocol => "UnsupportedProtocol",
            Self::TooManyRedirects => "TooManyRedirects",
            Self::InvalidResponse => "InvalidResponse",
            Self::ClientClosed => "ClientClosed",
            Self::Other => "TransportError",
        };
        f.write_str(label)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SdkTransportError {
    pub kind: SdkTransportErrorKind,
    pub message: String,
}

impl SdkTransportError {
    pub fn new(kind: SdkTransportErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }
}

impl std::fmt::Display for SdkTransportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.kind, self.message)
    }
}

impl std::error::Error for SdkTransportError {}

/// A transport-level request exposed to custom SDK transports.
#[derive(Clone, PartialEq, Eq)]
pub struct SdkRequest {
    pub method: String,
    pub url: String,
    pub timeout: Duration,
    pub headers: Vec<(String, String)>,
    pub body: Option<Vec<u8>>,
}

impl std::fmt::Debug for SdkRequest {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let header_names: Vec<_> = self.headers.iter().map(|(name, _)| name).collect();
        formatter
            .debug_struct("SdkRequest")
            .field("method", &self.method)
            .field("url", &"<redacted>")
            .field("timeout", &self.timeout)
            .field("header_names", &header_names)
            .field("body_bytes", &self.body.as_ref().map(Vec::len))
            .finish()
    }
}

/// Raw HTTP response returned by an SDK transport.
#[derive(Clone, PartialEq, Eq)]
pub struct SdkResponse {
    pub status_code: u16,
    pub body: Vec<u8>,
}

impl std::fmt::Debug for SdkResponse {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("SdkResponse")
            .field("status_code", &self.status_code)
            .field("body_bytes", &self.body.len())
            .finish()
    }
}

/// Replaceable synchronous transport seam for deterministic tests and custom
/// connection policies. `close` is called once when the client is closed.
pub trait SdkTransport: Send + Sync {
    /// Implementations must not call back into the owning `AgentRouterClient`
    /// from `send` or `close`; close waits for active sends to finish.
    fn send(&self, request: SdkRequest) -> Result<SdkResponse, SdkTransportError>;

    fn close(&self) {}
}

struct UreqTransport {
    agent: Mutex<Option<ureq::Agent>>,
}

impl UreqTransport {
    fn new(timeout: Duration) -> Self {
        Self {
            agent: Mutex::new(Some(
                ureq::AgentBuilder::new()
                    .redirects(0)
                    .timeout(timeout)
                    .build(),
            )),
        }
    }
}

impl SdkTransport for UreqTransport {
    fn send(&self, request: SdkRequest) -> Result<SdkResponse, SdkTransportError> {
        let agent = self
            .agent
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .as_ref()
            .cloned()
            .ok_or_else(|| {
                SdkTransportError::new(SdkTransportErrorKind::ClientClosed, "transport is closed")
            })?;
        let mut builder = agent.request(&request.method, &request.url);
        for (name, value) in request.headers {
            builder = builder.set(&name, &value);
        }
        let response = match request.body {
            Some(body) => builder.send_bytes(&body),
            None => builder.call(),
        };
        let response = match response {
            Ok(response) => response,
            Err(ureq::Error::Status(_, response)) => response,
            Err(ureq::Error::Transport(error)) => {
                return Err(SdkTransportError::new(
                    ureq_transport_kind(&error),
                    "request failed",
                ));
            }
        };
        let status_code = response.status();
        let mut body = Vec::new();
        response
            .into_reader()
            .read_to_end(&mut body)
            .map_err(|error| {
                SdkTransportError::new(
                    if error.kind() == std::io::ErrorKind::TimedOut {
                        SdkTransportErrorKind::ReadTimeout
                    } else {
                        SdkTransportErrorKind::ReadError
                    },
                    "response body read failed",
                )
            })?;
        Ok(SdkResponse { status_code, body })
    }

    fn close(&self) {
        self.agent
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .take();
    }
}

fn ureq_transport_kind(error: &ureq::Transport) -> SdkTransportErrorKind {
    use std::error::Error as _;
    use std::io;
    use ureq::ErrorKind;

    let io_kind = || {
        let mut source = error.source();
        while let Some(current) = source {
            if let Some(io_error) = current.downcast_ref::<io::Error>() {
                return Some(io_error.kind());
            }
            source = current.source();
        }
        None
    };
    match error.kind() {
        ErrorKind::InvalidUrl => SdkTransportErrorKind::InvalidUrl,
        ErrorKind::UnknownScheme => SdkTransportErrorKind::UnsupportedProtocol,
        ErrorKind::Dns | ErrorKind::ConnectionFailed => {
            if io_kind() == Some(io::ErrorKind::TimedOut) {
                SdkTransportErrorKind::ConnectTimeout
            } else {
                SdkTransportErrorKind::ConnectError
            }
        }
        ErrorKind::InsecureRequestHttpsOnly => SdkTransportErrorKind::ConnectError,
        ErrorKind::TooManyRedirects => SdkTransportErrorKind::TooManyRedirects,
        ErrorKind::BadStatus | ErrorKind::BadHeader => SdkTransportErrorKind::ProtocolError,
        ErrorKind::Io => {
            if io_kind() == Some(io::ErrorKind::TimedOut) {
                SdkTransportErrorKind::ReadTimeout
            } else {
                SdkTransportErrorKind::ReadError
            }
        }
        ErrorKind::InvalidProxyUrl | ErrorKind::ProxyConnect | ErrorKind::ProxyUnauthorized => {
            SdkTransportErrorKind::ProxyError
        }
        ErrorKind::HTTP => SdkTransportErrorKind::ProtocolError,
    }
}

fn api_error(status_code: u16, text: String) -> ClientError {
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
    ClientError::Api(AgentRouterError {
        status_code,
        code,
        message,
    })
}

/// Remove null fields while retaining explicit false and zero values.
pub fn clean(fields: impl IntoIterator<Item = (String, Value)>) -> Value {
    Value::Object(
        fields
            .into_iter()
            .filter(|(_, value)| !value.is_null())
            .collect::<Map<String, Value>>(),
    )
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ClientStatus {
    Open,
    Closing,
    Closed,
}

struct LifecycleState {
    status: ClientStatus,
    active_requests: usize,
}

struct RequestLifecycle {
    state: Mutex<LifecycleState>,
    changed: Condvar,
}

impl RequestLifecycle {
    fn new() -> Self {
        Self {
            state: Mutex::new(LifecycleState {
                status: ClientStatus::Open,
                active_requests: 0,
            }),
            changed: Condvar::new(),
        }
    }

    fn begin_request(&self) -> Option<ActiveRequest<'_>> {
        let mut state = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if state.status != ClientStatus::Open {
            return None;
        }
        state.active_requests += 1;
        Some(ActiveRequest { lifecycle: self })
    }

    fn end_request(&self) {
        let mut state = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        state.active_requests -= 1;
        if state.active_requests == 0 {
            self.changed.notify_all();
        }
    }

    fn begin_close(&self) -> bool {
        let mut state = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        match state.status {
            ClientStatus::Closed => return false,
            ClientStatus::Closing => {
                while state.status == ClientStatus::Closing {
                    state = self
                        .changed
                        .wait(state)
                        .unwrap_or_else(std::sync::PoisonError::into_inner);
                }
                return false;
            }
            ClientStatus::Open => {
                state.status = ClientStatus::Closing;
                self.changed.notify_all();
            }
        }
        while state.active_requests > 0 {
            state = self
                .changed
                .wait(state)
                .unwrap_or_else(std::sync::PoisonError::into_inner);
        }
        true
    }

    fn finish_close(&self) {
        let mut state = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        state.status = ClientStatus::Closed;
        self.changed.notify_all();
    }
}

struct ActiveRequest<'a> {
    lifecycle: &'a RequestLifecycle,
}

impl Drop for ActiveRequest<'_> {
    fn drop(&mut self) {
        self.lifecycle.end_request();
    }
}

struct FinishClose<'a> {
    lifecycle: &'a RequestLifecycle,
}

impl Drop for FinishClose<'_> {
    fn drop(&mut self) {
        self.lifecycle.finish_close();
    }
}

pub struct AgentRouterClient {
    base_url: String,
    api_key: Option<String>,
    timeout: Duration,
    transport: Arc<dyn SdkTransport>,
    lifecycle: RequestLifecycle,
}

impl AgentRouterClient {
    pub fn new(base_url: Option<&str>, api_key: Option<&str>, timeout: Option<Duration>) -> Self {
        let timeout = timeout.unwrap_or(Duration::from_secs(10));
        let transport: Arc<dyn SdkTransport> = Arc::new(UreqTransport::new(timeout));
        Self::with_transport_timeout(base_url, api_key, Some(timeout), transport)
    }

    pub fn with_transport(
        base_url: Option<&str>,
        api_key: Option<&str>,
        transport: Arc<dyn SdkTransport>,
    ) -> Self {
        Self::with_transport_timeout(base_url, api_key, None, transport)
    }

    /// Construct the client with a custom transport and optional request
    /// timeout. The configured value is included in each `SdkRequest` so a
    /// custom transport can enforce the same bound as the default adapter.
    pub fn with_transport_timeout(
        base_url: Option<&str>,
        api_key: Option<&str>,
        timeout: Option<Duration>,
        transport: Arc<dyn SdkTransport>,
    ) -> Self {
        let base_url = base_url
            .unwrap_or("http://127.0.0.1:8000")
            .trim_end_matches('/');
        Self {
            base_url: base_url.to_owned(),
            api_key: api_key.filter(|key| !key.is_empty()).map(str::to_owned),
            timeout: timeout.unwrap_or(Duration::from_secs(10)),
            transport,
            lifecycle: RequestLifecycle::new(),
        }
    }

    /// Close the client once. This waits for in-flight transport sends to
    /// finish, then closes the transport; requests started afterward fail with
    /// `ClientClosed`. Custom transports must not call back into this client
    /// from either callback.
    pub fn close(&self) {
        if self.lifecycle.begin_close() {
            let _finish = FinishClose {
                lifecycle: &self.lifecycle,
            };
            self.transport.close();
        }
    }

    fn request(&self, method: &str, path: &str, body: Option<Value>) -> Result<Value, ClientError> {
        let _active_request = self.lifecycle.begin_request().ok_or_else(|| {
            ClientError::Transport(SdkTransportError::new(
                SdkTransportErrorKind::ClientClosed,
                "client is closed",
            ))
        })?;
        let url = format!("{}{path}", self.base_url);
        let mut headers = Vec::new();
        if let Some(api_key) = &self.api_key {
            headers.push(("X-API-Key".into(), api_key.clone()));
        }
        let body = body.map(|value| {
            headers.push(("Content-Type".into(), "application/json".into()));
            value.to_string().into_bytes()
        });
        let response = self.transport.send(SdkRequest {
            method: method.into(),
            url,
            timeout: self.timeout,
            headers,
            body,
        });
        drop(_active_request);
        let response = response.map_err(ClientError::Transport)?;
        let text = String::from_utf8_lossy(&response.body).into_owned();
        if !(200..300).contains(&response.status_code) {
            return Err(api_error(response.status_code, text));
        }
        serde_json::from_slice(&response.body).map_err(|error| {
            ClientError::Transport(SdkTransportError::new(
                SdkTransportErrorKind::InvalidResponse,
                error.to_string(),
            ))
        })
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
            .ok_or_else(|| {
                ClientError::Transport(SdkTransportError::new(
                    SdkTransportErrorKind::InvalidResponse,
                    "expected a JSON array",
                ))
            })
    }

    pub fn hosts(&self) -> Result<Vec<Value>, ClientError> {
        self.request("GET", "/v1/hosts", None)?
            .as_array()
            .cloned()
            .ok_or_else(|| {
                ClientError::Transport(SdkTransportError::new(
                    SdkTransportErrorKind::InvalidResponse,
                    "expected a JSON array",
                ))
            })
    }

    pub fn classify(
        &self,
        task: &str,
        context_tokens: Option<serde_json::Number>,
        risk: Option<&str>,
        tools: Option<&[String]>,
    ) -> Result<Value, ClientError> {
        self.request(
            "POST",
            "/v1/classify",
            Some(clean([
                ("task".into(), json!(task)),
                ("context_tokens".into(), json!(context_tokens)),
                ("risk".into(), json!(risk)),
                ("tools".into(), json!(tools)),
            ])),
        )
    }

    pub fn route(
        &self,
        task: &str,
        prefer: Option<&str>,
        context_tokens: Option<serde_json::Number>,
        risk: Option<&str>,
        tools: Option<&[String]>,
        no_log: bool,
    ) -> Result<Value, ClientError> {
        self.request(
            "POST",
            "/v1/route",
            Some(clean([
                ("task".into(), json!(task)),
                ("prefer".into(), json!(prefer)),
                ("context_tokens".into(), json!(context_tokens)),
                ("risk".into(), json!(risk)),
                ("tools".into(), json!(tools)),
                ("no_log".into(), json!(no_log)),
            ])),
        )
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

impl Drop for AgentRouterClient {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::thread;

    struct FakeTransport {
        response: Result<SdkResponse, SdkTransportError>,
        request: std::sync::Mutex<Option<SdkRequest>>,
        closed: AtomicBool,
        close_count: std::sync::atomic::AtomicUsize,
    }

    impl SdkTransport for FakeTransport {
        fn send(&self, request: SdkRequest) -> Result<SdkResponse, SdkTransportError> {
            *self.request.lock().unwrap() = Some(request);
            self.response.clone()
        }

        fn close(&self) {
            self.closed.store(true, Ordering::Release);
            self.close_count
                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
        }
    }

    fn fake_transport(response: Result<SdkResponse, SdkTransportError>) -> Arc<FakeTransport> {
        Arc::new(FakeTransport {
            response,
            request: std::sync::Mutex::new(None),
            closed: AtomicBool::new(false),
            close_count: std::sync::atomic::AtomicUsize::new(0),
        })
    }

    #[test]
    fn closing_default_transport_drops_agent_and_rejects_direct_send() {
        let transport = UreqTransport::new(Duration::from_secs(1));
        assert!(transport.agent.lock().unwrap().is_some());

        transport.close();

        assert!(transport.agent.lock().unwrap().is_none());
        let error = transport
            .send(SdkRequest {
                method: "GET".into(),
                url: "http://127.0.0.1/health".into(),
                timeout: Duration::from_secs(1),
                headers: Vec::new(),
                body: None,
            })
            .unwrap_err();
        assert_eq!(error.kind, SdkTransportErrorKind::ClientClosed);
    }

    #[test]
    fn default_transport_error_display_does_not_echo_url_credentials() {
        let client = AgentRouterClient::new(
            Some("ftp://fixture-user:fixture-pass@fixture.invalid/private?token=secret"),
            None,
            Some(Duration::from_secs(1)),
        );

        let rendered = client.health().unwrap_err().to_string();

        assert!(rendered.contains("UnsupportedProtocol"));
        for sensitive in [
            "fixture-user",
            "fixture-pass",
            "fixture.invalid",
            "private",
            "secret",
        ] {
            assert!(
                !rendered.contains(sensitive),
                "leaked {sensitive}: {rendered}"
            );
        }
    }

    #[test]
    fn request_and_response_debug_redact_credentials_and_bodies() {
        let request = SdkRequest {
            method: "POST".into(),
            url: "https://fixture-user:fixture-pass@fixture.invalid/private?token=url-secret"
                .into(),
            timeout: Duration::from_secs(3),
            headers: vec![
                ("X-API-Key".into(), "api-key-secret".into()),
                ("Content-Type".into(), "application/json".into()),
            ],
            body: Some(b"prompt-secret".to_vec()),
        };
        let request_debug = format!("{request:?}");
        for sensitive in [
            "fixture-user",
            "fixture-pass",
            "fixture.invalid",
            "private",
            "url-secret",
            "api-key-secret",
            "prompt-secret",
        ] {
            assert!(
                !request_debug.contains(sensitive),
                "leaked {sensitive}: {request_debug}"
            );
        }
        assert!(request_debug.contains("POST"));
        assert!(request_debug.contains("body_bytes"));

        let response = SdkResponse {
            status_code: 200,
            body: b"response-secret".to_vec(),
        };
        let response_debug = format!("{response:?}");
        assert!(!response_debug.contains("response-secret"));
        assert!(response_debug.contains("200"));
        assert!(response_debug.contains("body_bytes"));
    }

    #[test]
    fn injected_transport_receives_normalized_request_and_client_closes_it_once() {
        let transport = fake_transport(Ok(SdkResponse {
            status_code: 200,
            body: br#"{"status":"ok"}"#.to_vec(),
        }));
        let client = AgentRouterClient::with_transport(
            Some("https://router.example/"),
            Some("sdk-test-key"),
            transport.clone(),
        );

        assert_eq!(client.health().unwrap(), json!({"status": "ok"}));
        assert_eq!(
            transport.request.lock().unwrap().as_ref().unwrap(),
            &SdkRequest {
                method: "GET".into(),
                url: "https://router.example/health".into(),
                timeout: Duration::from_secs(10),
                headers: vec![("X-API-Key".into(), "sdk-test-key".into())],
                body: None,
            }
        );

        client.close();
        client.close();
        assert!(transport.closed.load(Ordering::Acquire));
        assert!(matches!(
            client.health(),
            Err(ClientError::Transport(SdkTransportError {
                kind: SdkTransportErrorKind::ClientClosed,
                ..
            }))
        ));
        drop(client);
        assert_eq!(transport.close_count.load(Ordering::Acquire), 1);
    }

    #[test]
    fn close_waits_for_an_actual_in_flight_send_before_closing_transport() {
        struct BlockingTransport {
            started: Mutex<Option<std::sync::mpsc::Sender<()>>>,
            release: Mutex<std::sync::mpsc::Receiver<()>>,
            active: AtomicBool,
            closed_during_send: AtomicBool,
            close_count: std::sync::atomic::AtomicUsize,
        }

        impl SdkTransport for BlockingTransport {
            fn send(&self, _request: SdkRequest) -> Result<SdkResponse, SdkTransportError> {
                self.active.store(true, Ordering::Release);
                self.started
                    .lock()
                    .unwrap()
                    .take()
                    .unwrap()
                    .send(())
                    .unwrap();
                self.release.lock().unwrap().recv().unwrap();
                self.active.store(false, Ordering::Release);
                Ok(SdkResponse {
                    status_code: 200,
                    body: br#"{"status":"ok"}"#.to_vec(),
                })
            }

            fn close(&self) {
                if self.active.load(Ordering::Acquire) {
                    self.closed_during_send.store(true, Ordering::Release);
                }
                self.close_count
                    .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
            }
        }

        let (started_tx, started_rx) = std::sync::mpsc::channel();
        let (release_tx, release_rx) = std::sync::mpsc::channel();
        let transport = Arc::new(BlockingTransport {
            started: Mutex::new(Some(started_tx)),
            release: Mutex::new(release_rx),
            active: AtomicBool::new(false),
            closed_during_send: AtomicBool::new(false),
            close_count: std::sync::atomic::AtomicUsize::new(0),
        });
        let client = Arc::new(AgentRouterClient::with_transport(
            Some("http://router.example"),
            None,
            transport.clone(),
        ));
        let requesting_client = Arc::clone(&client);
        let request = thread::spawn(move || requesting_client.health());
        started_rx.recv_timeout(Duration::from_secs(5)).unwrap();
        let (closed_tx, closed_rx) = std::sync::mpsc::channel();
        let closing_client = Arc::clone(&client);
        let closing = thread::spawn(move || {
            closing_client.close();
            closed_tx.send(()).unwrap();
        });

        let deadline = std::time::Instant::now() + Duration::from_secs(5);
        let mut state = client.lifecycle.state.lock().unwrap();
        while state.status != ClientStatus::Closing {
            let remaining = deadline.saturating_duration_since(std::time::Instant::now());
            assert!(
                !remaining.is_zero(),
                "close did not enter its closing state"
            );
            let (next_state, wait) = client
                .lifecycle
                .changed
                .wait_timeout(state, remaining)
                .unwrap();
            state = next_state;
            assert!(
                !wait.timed_out() || state.status == ClientStatus::Closing,
                "close did not enter its closing state"
            );
        }
        assert!(closed_rx.try_recv().is_err());
        drop(state);

        release_tx.send(()).unwrap();
        assert_eq!(request.join().unwrap().unwrap(), json!({"status": "ok"}));
        closed_rx.recv_timeout(Duration::from_secs(5)).unwrap();
        closing.join().unwrap();
        assert!(!transport.closed_during_send.load(Ordering::Acquire));
        assert_eq!(transport.close_count.load(Ordering::Acquire), 1);
    }

    #[test]
    fn injected_transport_error_preserves_its_stable_category() {
        let transport = fake_transport(Err(SdkTransportError::new(
            SdkTransportErrorKind::ConnectTimeout,
            "fixture timeout",
        )));
        let client =
            AgentRouterClient::with_transport(Some("http://router.example"), None, transport);

        assert!(matches!(
            client.health(),
            Err(ClientError::Transport(SdkTransportError {
                kind: SdkTransportErrorKind::ConnectTimeout,
                message,
            })) if message == "fixture timeout"
        ));
    }

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
            .route("write docs", None, Some(0.into()), None, None, false)
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

    #[test]
    fn client_does_not_forward_api_keys_through_redirects() {
        let target = TcpListener::bind("127.0.0.1:0").unwrap();
        let target_address = target.local_addr().unwrap();
        target.set_nonblocking(true).unwrap();
        let forwarded = thread::spawn(move || {
            for _ in 0..40 {
                match target.accept() {
                    Ok((mut stream, _)) => {
                        let mut request = [0; 2048];
                        let _ = stream.read(&mut request);
                        let body = r#"{"status":"leaked"}"#;
                        let _ = write!(
                            stream,
                            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                            body.len()
                        );
                        return true;
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(5));
                    }
                    Err(error) => panic!("redirect target listener failed: {error}"),
                }
            }
            false
        });

        let redirect = TcpListener::bind("127.0.0.1:0").unwrap();
        let redirect_address = redirect.local_addr().unwrap();
        let redirect_server = thread::spawn(move || {
            let (mut stream, _) = redirect.accept().unwrap();
            let mut request = [0; 2048];
            let _ = stream.read(&mut request);
            write!(
                stream,
                "HTTP/1.1 302 Found\r\nLocation: http://{target_address}/leak\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .unwrap();
        });

        let url = format!("http://{redirect_address}");
        let client = AgentRouterClient::new(Some(&url), Some("secret"), None);
        let result = client.health();
        assert!(
            matches!(
                &result,
                Err(ClientError::Api(AgentRouterError {
                    status_code: 302,
                    ..
                }))
            ),
            "unexpected redirect response: {result:?}"
        );
        redirect_server.join().unwrap();
        assert!(!forwarded.join().unwrap());
    }
}
