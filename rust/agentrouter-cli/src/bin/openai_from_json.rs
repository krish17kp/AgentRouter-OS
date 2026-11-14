//! Offline Python/Rust compatibility probe for the Responses API adapter.
//!
//! The fixture transport never opens a network connection. The input key is
//! compared only inside the process and is never included in emitted JSON.

use std::cell::RefCell;

use agentrouter_cli::openai::{
    run_text_response, OpenAIRequest, OpenAITransport, TransportError, TransportResponse,
};
use serde_json::{json, Value};

struct FixtureTransport {
    expected_key: String,
    status: u16,
    body: Vec<u8>,
    transport_error: Option<TransportError>,
    observed: RefCell<Option<Value>>,
}

impl OpenAITransport for FixtureTransport {
    fn post(
        &self,
        request: &OpenAIRequest,
        timeout_seconds: u64,
        max_response_bytes: usize,
    ) -> Result<TransportResponse, TransportError> {
        *self.observed.borrow_mut() = Some(json!({
            "url": request.url(),
            "body": request.json_body(),
            "timeout_seconds": timeout_seconds,
            "max_response_bytes": max_response_bytes,
            "authorization_matches_fixture_key": request.authorization_header()
                == format!("Bearer {}", self.expected_key),
        }));
        if let Some(error) = self.transport_error {
            return Err(error);
        }
        if self.status >= 400 {
            return Err(TransportError::HttpStatus(self.status));
        }
        Ok(TransportResponse {
            status: self.status,
            body: self.body.clone(),
        })
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    std::io::stdin().read_line(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let body = request
        .get("response_body")
        .and_then(Value::as_str)
        .unwrap_or("")
        .as_bytes()
        .to_vec();
    let status = request
        .get("status")
        .and_then(Value::as_u64)
        .and_then(|value| u16::try_from(value).ok())
        .unwrap_or(200);
    let transport_error = match request.get("transport_error").and_then(Value::as_str) {
        Some("network") => Some(TransportError::Network),
        Some("http_status") => Some(TransportError::HttpStatus(status)),
        _ => None,
    };
    let key = request
        .get("api_key")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    let transport = FixtureTransport {
        expected_key: key.clone(),
        status,
        body,
        transport_error,
        observed: RefCell::new(None),
    };
    let max_output_tokens = request
        .get("max_output_tokens")
        .and_then(Value::as_i64)
        .and_then(|value| u32::try_from(value).ok())
        .unwrap_or(0);
    let result = run_text_response(
        &transport,
        request
            .get("model_id")
            .and_then(Value::as_str)
            .unwrap_or(""),
        request.get("prompt").and_then(Value::as_str).unwrap_or(""),
        &key,
        max_output_tokens,
    );
    let mut output = match result {
        Ok(text) => json!({"text": text}),
        Err(error) => json!({"error": error.to_string()}),
    };
    output["request"] = transport.observed.borrow().clone().unwrap_or(Value::Null);
    println!("{}", serde_json::to_string(&output)?);
    Ok(())
}
