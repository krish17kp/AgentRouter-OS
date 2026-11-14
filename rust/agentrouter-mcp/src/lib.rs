//! Read-only and dry-run MCP tools over the 2025-11-25 stdio protocol.
//!
//! This server implements only the five tools exported by
//! `agentrouter.mcp_server`. It never exposes process or model execution.

use std::{
    io::{self, BufRead, Write},
    path::PathBuf,
};

use agentrouter_api::{
    schemas::{ClassifyRequest, RouteRequest},
    service::{self, ServiceError},
};
use serde_json::{json, Map, Value};

const SUPPORTED_PROTOCOL_VERSIONS: &[&str] =
    &["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"];
const DEFAULT_PROTOCOL_VERSION: &str = "2025-11-25";
const MAX_LINE_BYTES: usize = 4 * 1024 * 1024;

#[derive(Debug, Clone)]
pub struct Server {
    home: PathBuf,
}

impl Server {
    pub fn new(home: PathBuf) -> Self {
        Self { home }
    }

    /// Handle one decoded JSON-RPC message. Notifications return `None`.
    pub fn handle(&self, message: &Value) -> Option<Value> {
        let object = match message.as_object() {
            Some(object) if object.get("jsonrpc").and_then(Value::as_str) == Some("2.0") => object,
            _ => return Some(rpc_error(Value::Null, -32600, "Invalid Request")),
        };
        let method = match object.get("method").and_then(Value::as_str) {
            Some(method) => method,
            None => return Some(rpc_error(Value::Null, -32600, "Invalid Request")),
        };
        let Some(id) = object.get("id") else {
            self.handle_notification(method);
            return None;
        };
        let id = id.clone();
        let params = object.get("params").unwrap_or(&Value::Null);

        match method {
            "initialize" => Some(self.initialize(id, params)),
            "ping" => Some(rpc_result(id, json!({}))),
            "tools/list" => Some(rpc_result(id, json!({"tools": tool_definitions()}))),
            "tools/call" => Some(rpc_result(id, self.call_tool(params))),
            "resources/list" | "resources/templates/list" => Some(rpc_result(
                id,
                json!({"resources": [], "resourceTemplates": []}),
            )),
            "prompts/list" => Some(rpc_result(id, json!({"prompts": []}))),
            _ => Some(rpc_error(id, -32601, "Method not found")),
        }
    }

    fn initialize(&self, id: Value, params: &Value) -> Value {
        let requested = params
            .get("protocolVersion")
            .and_then(Value::as_str)
            .unwrap_or(DEFAULT_PROTOCOL_VERSION);
        let protocol_version = if SUPPORTED_PROTOCOL_VERSIONS.contains(&requested) {
            requested
        } else {
            DEFAULT_PROTOCOL_VERSION
        };
        rpc_result(
            id,
            json!({
                "protocolVersion": protocol_version,
                "capabilities": {
                    "experimental": {},
                    "prompts": {"listChanged": false},
                    "resources": {"subscribe": false, "listChanged": false},
                    "tools": {"listChanged": false}
                },
                "serverInfo": {
                    "name": "agentrouter",
                    "version": agentrouter_core::package_version()
                }
            }),
        )
    }

    fn handle_notification(&self, method: &str) {
        // These notifications have no application-side state in this server.
        if !matches!(
            method,
            "notifications/initialized" | "notifications/cancelled"
        ) {
            eprintln!("agentrouter-mcp: ignored notification {method}");
        }
    }

    fn call_tool(&self, params: &Value) -> Value {
        let Some(name) = params.get("name").and_then(Value::as_str) else {
            return tool_error("tool name is required");
        };
        let empty = Value::Object(Map::new());
        let arguments = params.get("arguments").unwrap_or(&empty);
        let result = match name {
            "route" => self.route(arguments),
            "classify" => self.classify(arguments),
            "explain" => self.explain(arguments),
            "list_models" => self.list_models(),
            "list_hosts" => Ok(json!({"result": service::list_hosts()})),
            _ => return tool_error(&format!("unknown tool '{name}'")),
        };
        match result {
            Ok(value) => tool_success(value),
            Err(message) => tool_error(&message),
        }
    }

    fn classify(&self, arguments: &Value) -> Result<Value, String> {
        let request = classify_request(arguments)?;
        service::classify_task(&request).map_err(safe_service_error)
    }

    fn route(&self, arguments: &Value) -> Result<Value, String> {
        let classify = classify_request(arguments)?;
        let prefer = optional_string(arguments, "prefer")?;
        let request = RouteRequest {
            classify,
            prefer,
            no_log: false,
        };
        service::route_task(&self.home, &request).map_err(safe_service_error)
    }

    fn explain(&self, arguments: &Value) -> Result<Value, String> {
        let decision_id = required_string(arguments, "decision_id")?;
        service::get_decision(&self.home, decision_id)
            .map(|result| json!({"result": result}))
            .map_err(safe_service_error)
    }

    fn list_models(&self) -> Result<Value, String> {
        service::list_models(&self.home)
            .map(|result| json!({"result": result}))
            .map_err(safe_service_error)
    }
}

/// Run the MCP process until stdin reaches EOF. stdout is protocol-only.
pub fn run_stdio(server: &Server) -> io::Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut input = stdin.lock();
    let mut output = stdout.lock();
    let mut line = Vec::new();

    loop {
        line.clear();
        let Some(within_limit) = read_bounded_line(&mut input, &mut line)? else {
            break;
        };
        if !within_limit {
            write_message(
                &mut output,
                &rpc_error(Value::Null, -32700, "Message is too large"),
            )?;
            continue;
        }
        let response = match serde_json::from_slice::<Value>(&line) {
            Ok(message) => server.handle(&message),
            Err(_) => Some(rpc_error(Value::Null, -32700, "Parse error")),
        };
        if let Some(response) = response {
            write_message(&mut output, &response)?;
        }
    }
    Ok(())
}

/// Read one newline-delimited frame without allocating beyond the protocol cap.
/// Oversized frames are drained in place so the next client message stays aligned.
fn read_bounded_line(input: &mut impl BufRead, line: &mut Vec<u8>) -> io::Result<Option<bool>> {
    line.clear();
    let mut oversized = false;
    loop {
        let available = input.fill_buf()?;
        if available.is_empty() {
            return Ok(if line.is_empty() && !oversized {
                None
            } else {
                Some(!oversized)
            });
        }

        let newline = available.iter().position(|byte| *byte == b'\n');
        let consumed = newline.map_or(available.len(), |position| position + 1);
        if !oversized {
            if line.len().saturating_add(consumed) <= MAX_LINE_BYTES {
                line.extend_from_slice(&available[..consumed]);
            } else {
                oversized = true;
            }
        }
        input.consume(consumed);
        if newline.is_some() {
            return Ok(Some(!oversized));
        }
    }
}

fn write_message(output: &mut impl Write, message: &Value) -> io::Result<()> {
    serde_json::to_writer(&mut *output, message)?;
    output.write_all(b"\n")?;
    output.flush()
}

fn tool_definitions() -> Value {
    serde_json::from_str(include_str!("../../../contracts/mcp/v1/tools.json"))
        .expect("committed MCP tools contract must be valid JSON")
}

fn rpc_result(id: Value, result: Value) -> Value {
    json!({"jsonrpc": "2.0", "id": id, "result": result})
}

fn rpc_error(id: Value, code: i64, message: &str) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": {"code": code, "message": message}
    })
}

fn tool_success(value: Value) -> Value {
    let text = serde_json::to_string_pretty(&value).unwrap_or_else(|_| "{}".to_string());
    json!({
        "content": [{"type": "text", "text": text}],
        "structuredContent": value,
        "isError": false
    })
}

fn tool_error(message: &str) -> Value {
    json!({
        "content": [{"type": "text", "text": message}],
        "isError": true
    })
}

fn safe_service_error(error: ServiceError) -> String {
    match error {
        ServiceError::Validation(message) => message,
        ServiceError::Registry(_) => {
            "registry unavailable or invalid; run 'agentrouter doctor' locally for details".into()
        }
        ServiceError::Internal(_) => "internal server error".into(),
    }
}

fn classify_request(arguments: &Value) -> Result<ClassifyRequest, String> {
    let task = required_string(arguments, "task")?.to_string();
    let context_tokens = match arguments.get("context_tokens") {
        None | Some(Value::Null) => None,
        Some(value) => Some(
            agentrouter_core::pydantic_integer_from_value(value)
                .map_err(|_| "context_tokens must be an integer".to_string())?,
        ),
    };
    let risk = match arguments.get("risk") {
        None | Some(Value::Null) => None,
        Some(value) => Some(
            serde_json::from_value(value.clone())
                .map_err(|_| "risk must be 'low', 'medium' or 'high'".to_string())?,
        ),
    };
    let tools = match arguments.get("tools") {
        None | Some(Value::Null) => None,
        Some(value) => Some(
            serde_json::from_value(value.clone())
                .map_err(|_| "tools must be a list of strings".to_string())?,
        ),
    };
    let request = ClassifyRequest {
        task,
        context_tokens,
        risk,
        tools,
    };
    request.validate().map_err(|error| error.to_string())?;
    Ok(request)
}

fn required_string<'a>(arguments: &'a Value, key: &str) -> Result<&'a str, String> {
    arguments
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{key} must be a string"))
}

fn optional_string(arguments: &Value, key: &str) -> Result<Option<String>, String> {
    match arguments.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value.clone())),
        Some(_) => Err(format!("{key} must be a string")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn advertises_only_the_five_safe_tools() {
        let tools = tool_definitions();
        let names: Vec<_> = tools
            .as_array()
            .expect("tools is an array")
            .iter()
            .map(|tool| tool["name"].as_str().unwrap())
            .collect();
        assert_eq!(
            names,
            ["route", "classify", "explain", "list_models", "list_hosts"]
        );
        assert!(!names.iter().any(|name| name.contains("exec")));
    }

    #[test]
    fn negotiates_supported_protocol_and_lists_stable_tools() {
        let server = Server::new(PathBuf::from("/tmp/agentrouter-mcp-test"));
        let init = server
            .handle(&json!({
                "jsonrpc":"2.0", "id":1, "method":"initialize",
                "params":{"protocolVersion":"2025-11-25"}
            }))
            .unwrap();
        assert_eq!(init["result"]["protocolVersion"], "2025-11-25");
        assert_eq!(init["result"]["serverInfo"]["name"], "agentrouter");
        let tools = server
            .handle(&json!({"jsonrpc":"2.0", "id":2, "method":"tools/list"}))
            .unwrap();
        assert_eq!(tools["result"]["tools"].as_array().unwrap().len(), 5);
    }

    #[test]
    fn notifications_have_no_response_and_unknown_tools_are_safe_errors() {
        let server = Server::new(PathBuf::from("/tmp/agentrouter-mcp-test"));
        assert!(server
            .handle(&json!({"jsonrpc":"2.0", "method":"notifications/initialized"}))
            .is_none());
        let response = server
            .handle(&json!({
                "jsonrpc":"2.0", "id":3, "method":"tools/call",
                "params":{"name":"execute", "arguments":{}}
            }))
            .unwrap();
        assert_eq!(response["result"]["isError"], true);
        assert!(response["result"]["content"][0]["text"]
            .as_str()
            .unwrap()
            .contains("unknown tool"));
    }

    #[test]
    fn oversized_frame_is_bounded_and_does_not_consume_the_next_message() {
        let mut bytes = vec![b'x'; MAX_LINE_BYTES + 1];
        bytes.extend_from_slice(b"\n{}\n");
        let mut input = Cursor::new(bytes);
        let mut line = Vec::new();

        assert_eq!(
            read_bounded_line(&mut input, &mut line).unwrap(),
            Some(false)
        );
        assert!(line.len() <= MAX_LINE_BYTES);
        assert_eq!(
            read_bounded_line(&mut input, &mut line).unwrap(),
            Some(true)
        );
        assert_eq!(line, b"{}\n");
    }
}
