//! Offline-testable contract for the bounded OpenAI Responses API adapter.
//!
//! This mirrors the validation, request body, safe error surface, response-size
//! cap, and output extraction in `agentrouter.openai_adapter`. A concrete HTTPS
//! transport remains a separate deployment adapter; this module never retries.

use std::fmt;
use std::io::Read;

use serde_json::{json, Value};

pub const RESPONSES_URL: &str = "https://api.openai.com/v1/responses";
pub const MAX_RESPONSE_BYTES: usize = 2_000_000;
pub const MAX_OUTPUT_TOKENS: u32 = 4_096;
pub const TIMEOUT_SECONDS: u64 = 60;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OpenAIAdapterError {
    MissingInput,
    InvalidOutputLimit,
    HttpStatus(u16),
    Transport,
    ResponseTooLarge,
    InvalidJson,
    Incomplete,
    MissingOutput,
    Refusal,
    EmptyText,
}

impl fmt::Display for OpenAIAdapterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingInput => f.write_str("OpenAI model, prompt, and key are required"),
            Self::InvalidOutputLimit => f.write_str("OpenAI output limit must be positive"),
            Self::HttpStatus(code) => write!(f, "OpenAI request failed with HTTP {code}"),
            Self::Transport => f.write_str("OpenAI request failed or timed out"),
            Self::ResponseTooLarge => f.write_str("OpenAI response exceeded the size limit"),
            Self::InvalidJson => f.write_str("OpenAI returned invalid JSON"),
            Self::Incomplete => f.write_str("OpenAI response did not complete"),
            Self::MissingOutput => f.write_str("OpenAI response had no output items"),
            Self::Refusal => f.write_str("OpenAI refused this request"),
            Self::EmptyText => f.write_str("OpenAI response contained no text output"),
        }
    }
}

impl std::error::Error for OpenAIAdapterError {}

/// Request facts needed by a transport. Its API key is intentionally private
/// and it does not implement `Debug`, preventing accidental secret logging.
pub struct OpenAIRequest {
    model_id: String,
    prompt: String,
    api_key: String,
    max_output_tokens: u32,
}

impl OpenAIRequest {
    pub fn url(&self) -> &'static str {
        RESPONSES_URL
    }

    pub fn authorization_header(&self) -> String {
        format!("Bearer {}", self.api_key)
    }

    pub fn json_body(&self) -> Value {
        json!({
            "model": self.model_id,
            "input": self.prompt,
            "max_output_tokens": self.max_output_tokens,
            "store": false,
            "stream": false,
        })
    }
}

pub fn build_request(
    model_id: &str,
    prompt: &str,
    api_key: &str,
    max_output_tokens: u32,
) -> Result<OpenAIRequest, OpenAIAdapterError> {
    if model_id.is_empty() || prompt.is_empty() || api_key.trim().is_empty() {
        return Err(OpenAIAdapterError::MissingInput);
    }
    if max_output_tokens == 0 {
        return Err(OpenAIAdapterError::InvalidOutputLimit);
    }
    Ok(OpenAIRequest {
        model_id: model_id.to_owned(),
        prompt: prompt.to_owned(),
        api_key: api_key.to_owned(),
        max_output_tokens: max_output_tokens.min(MAX_OUTPUT_TOKENS),
    })
}

pub struct TransportResponse {
    pub status: u16,
    pub body: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransportError {
    HttpStatus(u16),
    Network,
}

/// HTTPS implementations must honor both bounds and return at most
/// `max_response_bytes + 1` bytes so the caller can detect overflow.
pub trait OpenAITransport {
    fn post(
        &self,
        request: &OpenAIRequest,
        timeout_seconds: u64,
        max_response_bytes: usize,
    ) -> Result<TransportResponse, TransportError>;
}

/// Production HTTPS transport. Redirects are disabled so the bearer token
/// cannot be forwarded to another origin; response bodies are read with a hard
/// cap even when the server streams an oversized response.
pub struct HttpsOpenAITransport {
    agent: ureq::Agent,
}

impl HttpsOpenAITransport {
    pub fn new() -> Result<Self, OpenAIAdapterError> {
        let agent = ureq::AgentBuilder::new().redirects(0).build();
        Ok(Self { agent })
    }
}

impl OpenAITransport for HttpsOpenAITransport {
    fn post(
        &self,
        request: &OpenAIRequest,
        timeout_seconds: u64,
        max_response_bytes: usize,
    ) -> Result<TransportResponse, TransportError> {
        let payload =
            serde_json::to_vec(&request.json_body()).map_err(|_| TransportError::Network)?;
        let response = self
            .agent
            .post(request.url())
            .set("Authorization", &request.authorization_header())
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(timeout_seconds))
            .send_bytes(&payload)
            .map_err(|error| match error {
                ureq::Error::Status(status, _) => TransportError::HttpStatus(status),
                ureq::Error::Transport(_) => TransportError::Network,
            })?;
        let status = response.status();
        let mut body = Vec::with_capacity(max_response_bytes.min(64 * 1024));
        response
            .into_reader()
            .take(max_response_bytes.saturating_add(1) as u64)
            .read_to_end(&mut body)
            .map_err(|_| TransportError::Network)?;
        Ok(TransportResponse { status, body })
    }
}

/// Make a single bounded Responses API operation using the provided transport.
pub fn run_text_response<T: OpenAITransport>(
    transport: &T,
    model_id: &str,
    prompt: &str,
    api_key: &str,
    max_output_tokens: u32,
) -> Result<String, OpenAIAdapterError> {
    let request = build_request(model_id, prompt, api_key, max_output_tokens)?;
    let response = transport
        .post(&request, TIMEOUT_SECONDS, MAX_RESPONSE_BYTES)
        .map_err(|error| match error {
            TransportError::HttpStatus(code) => OpenAIAdapterError::HttpStatus(code),
            TransportError::Network => OpenAIAdapterError::Transport,
        })?;
    if response.status >= 400 {
        return Err(OpenAIAdapterError::HttpStatus(response.status));
    }
    if response.body.len() > MAX_RESPONSE_BYTES {
        return Err(OpenAIAdapterError::ResponseTooLarge);
    }
    let payload: Value =
        serde_json::from_slice(&response.body).map_err(|_| OpenAIAdapterError::InvalidJson)?;
    if payload.get("status").and_then(Value::as_str) != Some("completed") {
        return Err(OpenAIAdapterError::Incomplete);
    }
    let output = payload
        .get("output")
        .and_then(Value::as_array)
        .ok_or(OpenAIAdapterError::MissingOutput)?;
    let mut parts = Vec::new();
    for item in output {
        if item.get("type").and_then(Value::as_str) != Some("message")
            || item.get("role").and_then(Value::as_str) != Some("assistant")
        {
            continue;
        }
        let Some(content) = item.get("content").and_then(Value::as_array) else {
            continue;
        };
        for part in content {
            match part.get("type").and_then(Value::as_str) {
                Some("refusal") => return Err(OpenAIAdapterError::Refusal),
                Some("output_text") => {
                    if let Some(text) = part.get("text").and_then(Value::as_str) {
                        parts.push(text.to_owned());
                    }
                }
                _ => {}
            }
        }
    }
    if parts.is_empty() || !parts.iter().any(|part| !part.trim().is_empty()) {
        return Err(OpenAIAdapterError::EmptyText);
    }
    Ok(parts.join("\n"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    type ObservedRequest = (String, String, Value, u64, usize);

    struct FakeTransport {
        response: RefCell<Result<TransportResponse, TransportError>>,
        observed: RefCell<Option<ObservedRequest>>,
    }

    impl OpenAITransport for FakeTransport {
        fn post(
            &self,
            request: &OpenAIRequest,
            timeout_seconds: u64,
            max_response_bytes: usize,
        ) -> Result<TransportResponse, TransportError> {
            *self.observed.borrow_mut() = Some((
                request.url().to_owned(),
                request.authorization_header(),
                request.json_body(),
                timeout_seconds,
                max_response_bytes,
            ));
            std::mem::replace(
                &mut *self.response.borrow_mut(),
                Err(TransportError::Network),
            )
        }
    }

    fn fake(body: Value) -> FakeTransport {
        FakeTransport {
            response: RefCell::new(Ok(TransportResponse {
                status: 200,
                body: serde_json::to_vec(&body).unwrap(),
            })),
            observed: RefCell::new(None),
        }
    }

    #[test]
    fn builds_bounded_private_non_streaming_request_and_extracts_text() {
        let transport = fake(json!({
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": "Hello"},
                    {"type": "output_text", "text": "world"}
                ]}
            ]
        }));
        let text = run_text_response(&transport, "gpt-test", "prompt", "secret", 99_999).unwrap();
        assert_eq!(text, "Hello\nworld");
        let observed = transport.observed.borrow();
        let (url, authorization, body, timeout, max_bytes) = observed.as_ref().unwrap();
        assert_eq!(url, RESPONSES_URL);
        assert_eq!(authorization, "Bearer secret");
        assert_eq!(body["model"], "gpt-test");
        assert_eq!(body["input"], "prompt");
        assert_eq!(body["max_output_tokens"], MAX_OUTPUT_TOKENS);
        assert_eq!(body["store"], false);
        assert_eq!(body["stream"], false);
        assert_eq!(*timeout, TIMEOUT_SECONDS);
        assert_eq!(*max_bytes, MAX_RESPONSE_BYTES);
    }

    #[test]
    fn validation_happens_before_the_transport() {
        for (model, prompt, key, limit, expected) in [
            ("", "p", "k", 1, OpenAIAdapterError::MissingInput),
            ("m", "", "k", 1, OpenAIAdapterError::MissingInput),
            ("m", "p", "   ", 1, OpenAIAdapterError::MissingInput),
            ("m", "p", "k", 0, OpenAIAdapterError::InvalidOutputLimit),
        ] {
            assert!(matches!(
                build_request(model, prompt, key, limit),
                Err(error) if error == expected
            ));
        }
    }

    #[test]
    fn safe_errors_cover_http_network_size_and_response_shape() {
        let transport = FakeTransport {
            response: RefCell::new(Err(TransportError::HttpStatus(429))),
            observed: RefCell::new(None),
        };
        assert_eq!(
            run_text_response(&transport, "m", "p", "secret", 10).unwrap_err(),
            OpenAIAdapterError::HttpStatus(429)
        );

        let transport = FakeTransport {
            response: RefCell::new(Err(TransportError::Network)),
            observed: RefCell::new(None),
        };
        assert_eq!(
            run_text_response(&transport, "m", "p", "secret", 10).unwrap_err(),
            OpenAIAdapterError::Transport
        );

        for (body, expected) in [
            (vec![b'x'; MAX_RESPONSE_BYTES + 1], OpenAIAdapterError::ResponseTooLarge),
            (b"not-json".to_vec(), OpenAIAdapterError::InvalidJson),
            (br#"{"status":"in_progress","output":[]}"#.to_vec(), OpenAIAdapterError::Incomplete),
            (br#"{"status":"completed"}"#.to_vec(), OpenAIAdapterError::MissingOutput),
            (br#"{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"refusal"}]}]}"#.to_vec(), OpenAIAdapterError::Refusal),
            (br#"{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"  "}]}]}"#.to_vec(), OpenAIAdapterError::EmptyText),
        ] {
            let transport = FakeTransport {
                response: RefCell::new(Ok(TransportResponse { status: 200, body })),
                observed: RefCell::new(None),
            };
            assert_eq!(
                run_text_response(&transport, "m", "p", "secret", 10).unwrap_err(),
                expected
            );
        }
    }
}
