//! Bounded live provider catalog refresh for the unified Rust CLI.
//!
//! Provider endpoints are fixed HTTPS URLs. Redirects are disabled, response
//! bodies are capped, API keys are sent only in Authorization headers, and the
//! manual registry is never modified.

use std::collections::HashSet;
use std::io::{Cursor, Read};
use std::path::{Path, PathBuf};
use std::time::Duration;

use chrono::{Local, SecondsFormat, Utc};
use serde_json::{json, Value};

const OPENROUTER_MODELS_URL: &str = "https://openrouter.ai/api/v1/models";
const OPENAI_MODELS_URL: &str = "https://api.openai.com/v1/models";
const MAX_RESPONSE_BYTES: usize = 16 * 1024 * 1024;
const TIMEOUT_SECONDS: u64 = 20;
const GENERATED_SUFFIX: &str = ".generated.yaml";

fn json_to_yaml(value: Value) -> Result<serde_yaml::Value, String> {
    match value {
        Value::Null => Ok(serde_yaml::Value::Null),
        Value::Bool(value) => Ok(serde_yaml::Value::Bool(value)),
        Value::Number(value) => {
            let number = if let Some(value) = value.as_i64() {
                serde_yaml::Number::from(value)
            } else if let Some(value) = value.as_u64() {
                serde_yaml::Number::from(value)
            } else if value.is_f64() {
                let value = value
                    .as_f64()
                    .ok_or("generated catalog number is outside the YAML range")?;
                serde_yaml::Number::from(value)
            } else {
                return Err("generated catalog number is outside the YAML range".to_owned());
            };
            Ok(serde_yaml::Value::Number(number))
        }
        Value::String(value) => Ok(serde_yaml::Value::String(value)),
        Value::Array(values) => values
            .into_iter()
            .map(json_to_yaml)
            .collect::<Result<Vec<_>, _>>()
            .map(serde_yaml::Value::Sequence),
        Value::Object(values) => {
            let mut mapping = serde_yaml::Mapping::new();
            for (key, value) in values {
                mapping.insert(key, json_to_yaml(value)?);
            }
            Ok(serde_yaml::Value::Mapping(mapping))
        }
    }
}

#[derive(Debug)]
pub struct RefreshResult {
    pub source_url: &'static str,
    pub entries: Vec<agentrouter_registry::ModelEntry>,
    pub warnings: Vec<String>,
}

fn provider_config(provider: &str) -> Option<(&'static str, &'static str)> {
    match provider {
        "openrouter" => Some((OPENROUTER_MODELS_URL, "OPENROUTER_API_KEY")),
        "openai" => Some((OPENAI_MODELS_URL, "OPENAI_API_KEY")),
        _ => None,
    }
}

fn fetch_json_at(url: &str, api_key: Option<&str>, agent: &ureq::Agent) -> Result<Value, String> {
    let mut request = agent.get(url).set("User-Agent", "agentrouter-os");
    if let Some(api_key) = api_key.filter(|key| !key.is_empty()) {
        request = request.set("Authorization", &format!("Bearer {api_key}"));
    }
    let response = match request.call() {
        Ok(response) => response,
        Err(ureq::Error::Status(status, _)) => {
            return Err(format!("provider returned HTTP {status} for {url}"))
        }
        Err(ureq::Error::Transport(_)) => return Err(format!("network error reaching {url}")),
    };
    if !(200..300).contains(&response.status()) {
        return Err(format!(
            "provider returned HTTP {} for {url}",
            response.status()
        ));
    }
    let mut body = Vec::new();
    response
        .into_reader()
        .take((MAX_RESPONSE_BYTES + 1) as u64)
        .read_to_end(&mut body)
        .map_err(|_| format!("network error reading catalog from {url}"))?;
    if body.len() > MAX_RESPONSE_BYTES {
        return Err(format!(
            "provider response exceeded the {MAX_RESPONSE_BYTES}-byte limit"
        ));
    }
    serde_json::from_slice(&body).map_err(|_| "provider response is not valid JSON".to_owned())
}

fn http_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .redirects(0)
        .timeout_connect(Duration::from_secs(TIMEOUT_SECONDS))
        .timeout_read(Duration::from_secs(TIMEOUT_SECONDS))
        .timeout_write(Duration::from_secs(TIMEOUT_SECONDS))
        .build()
}

/// Fetch and map the current provider catalog using only the provider's fixed
/// endpoint and environment key. This function never writes files.
pub fn fetch_catalog(
    provider: &str,
    limit: usize,
    match_id: Option<&str>,
) -> Result<RefreshResult, String> {
    let Some((source_url, key_env)) = provider_config(provider) else {
        return Err(format!("unsupported refresh provider '{provider}'"));
    };
    if limit == 0 {
        return Err("limit must be at least 1".to_owned());
    }
    let api_key = std::env::var(key_env).ok().filter(|key| !key.is_empty());
    if provider == "openai" && api_key.is_none() {
        return Err(
            "OpenAI refresh requires OPENAI_API_KEY (a read-only key is enough); set it in your environment and retry"
                .to_owned(),
        );
    }
    let payload = fetch_json_at(source_url, api_key.as_deref(), &http_agent())?;
    let today = Local::now().date_naive();
    let (entries, warnings) = if provider == "openrouter" {
        agentrouter_registry::refresh::openrouter_from_payload(&payload, limit, match_id, today)
    } else {
        agentrouter_registry::refresh::openai_from_payload(&payload, limit, match_id, today)
    }
    .map_err(|error| error.to_string())?;
    Ok(RefreshResult {
        source_url,
        entries,
        warnings,
    })
}

/// Read prior generated model IDs for report-only deprecation candidates.
/// Corrupt or absent prior files are treated as an empty baseline, matching
/// the Python refresh command.
pub fn previous_model_ids(registry: &Path, provider: &str) -> HashSet<String> {
    if !valid_provider(provider) {
        return HashSet::new();
    }
    let path = registry.join(format!("models.{provider}{GENERATED_SUFFIX}"));
    let Ok(text) = std::fs::read_to_string(path) else {
        return HashSet::new();
    };
    let Ok(raw) = serde_yaml::from_str::<Value>(&text) else {
        return HashSet::new();
    };
    raw.get("models")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|model| model.get("model_id").and_then(Value::as_str))
        .filter(|model_id| !model_id.is_empty())
        .map(str::to_owned)
        .collect()
}

/// Serialize generated metadata and atomically replace only the provider's
/// generated file. The manually curated models.yaml is never written.
pub fn write_generated_catalog(
    registry: &Path,
    provider: &str,
    source_url: &str,
    entries: &[agentrouter_registry::ModelEntry],
    limit: usize,
    match_id: Option<&str>,
) -> Result<PathBuf, String> {
    if !valid_provider(provider) {
        return Err(format!("invalid provider id: {provider:?}"));
    }
    let models = entries
        .iter()
        .map(|entry| {
            let mut value = serde_json::to_value(entry).map_err(|error| error.to_string())?;
            if let Value::Object(fields) = &mut value {
                fields.retain(|_, value| !value.is_null());
            }
            Ok(value)
        })
        .collect::<Result<Vec<_>, String>>()?;
    let fetched_at = Utc::now().to_rfc3339_opts(SecondsFormat::AutoSi, true);
    let document = json!({
        "provenance": {
            "provider": provider,
            "source_url": source_url,
            "fetched_at": fetched_at,
            "count": entries.len(),
            "tool_version": agentrouter_core::package_version(),
            "cli_args": {
                "limit": limit,
                "match": match_id,
            },
        },
        "models": models,
    });
    let yaml =
        serde_yaml::to_string(&json_to_yaml(document)?).map_err(|error| error.to_string())?;
    let yaml = yaml.strip_prefix("---\n").unwrap_or(&yaml);
    let header = format!(
        "# AUTO-GENERATED by `agentrouter providers refresh {provider}` — do not hand-edit.\n# Manual models.yaml always wins on collision. Delete this file to revert.\n"
    );
    let contents = format!("{header}{yaml}");
    let file_name = format!("models.{provider}{GENERATED_SUFFIX}");
    let parent = cap_std::fs::Dir::open_ambient_dir(registry, cap_std::ambient_authority())
        .map_err(|error| format!("cannot open registry directory: {error}"))?;
    let mut cursor = Cursor::new(contents.into_bytes());
    super::atomic_replace(&parent, Path::new(&file_name), &mut cursor, None)?;
    Ok(registry.join(file_name))
}

fn valid_provider(provider: &str) -> bool {
    !provider.is_empty()
        && provider.chars().all(|character| {
            character.is_ascii_alphanumeric() || character == '-' || character == '_'
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    fn local_agent() -> ureq::Agent {
        ureq::AgentBuilder::new()
            .redirects(0)
            .timeout(Duration::from_secs(2))
            .build()
    }

    fn serve_once(response: String) -> (String, thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = Vec::new();
            let mut byte = [0_u8; 1];
            while !request.ends_with(b"\r\n\r\n") {
                if stream.read_exact(&mut byte).is_err() {
                    break;
                }
                request.push(byte[0]);
            }
            stream.write_all(response.as_bytes()).unwrap();
            String::from_utf8_lossy(&request).into_owned()
        });
        (format!("http://{address}/catalog"), server)
    }

    #[test]
    fn bounded_fetch_sends_auth_only_in_header_and_parses_json() {
        let (url, server) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"data\":[]}".to_owned(),
        );
        let request = fetch_json_at(&url, Some("sk-test-secret"), &local_agent()).unwrap();
        assert_eq!(request, json!({ "data": [] }));
        let request = server.join().unwrap();
        assert!(request.contains("Authorization: Bearer sk-test-secret\r\n"));
        assert!(request.contains("User-Agent: agentrouter-os\r\n"));
    }

    #[test]
    fn redirect_is_returned_as_status_and_never_followed() {
        let sink = TcpListener::bind("127.0.0.1:0").unwrap();
        sink.set_nonblocking(true).unwrap();
        let sink_url = format!(
            "http://{}/should-not-receive-key",
            sink.local_addr().unwrap()
        );
        let (url, server) = serve_once(format!(
            "HTTP/1.1 302 Found\r\nLocation: {sink_url}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        ));
        let error = fetch_json_at(&url, Some("sk-never-forward"), &local_agent()).unwrap_err();
        assert!(error.contains("HTTP 302"));
        let original_request = server.join().unwrap();
        assert!(original_request.contains("Authorization: Bearer sk-never-forward"));
        assert!(sink.accept().is_err());
    }

    #[test]
    fn response_size_is_bounded() {
        let body = " ".repeat(MAX_RESPONSE_BYTES + 1);
        let (url, server) = serve_once(format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        ));
        let error = fetch_json_at(&url, None, &local_agent()).unwrap_err();
        assert!(error.contains("exceeded the"));
        let _ = server.join().unwrap();
    }

    #[test]
    fn generated_write_is_atomic_overwrites_only_provider_file_and_keeps_manual_registry() {
        let registry = tempfile::tempdir().unwrap();
        assert!(previous_model_ids(registry.path(), "../../outside").is_empty());
        assert!(write_generated_catalog(
            registry.path(),
            "../../outside",
            OPENROUTER_MODELS_URL,
            &[],
            25,
            None,
        )
        .is_err());
        let manual = registry.path().join("models.yaml");
        std::fs::write(&manual, "models: [manual]\n").unwrap();
        let generated = registry.path().join("models.openrouter.generated.yaml");
        std::fs::write(&generated, "old catalog").unwrap();
        let mut entry = agentrouter_registry::refresh::map_openrouter_model_on(
            &json!({
                "id": "vendor/sample",
                "context_length": 8192,
                "pricing": {"prompt": "0.00002", "completion": "0.0001"}
            }),
            Utc::now().date_naive(),
        )
        .unwrap();
        entry.input_price_per_million = Some(0.00002);
        let written = write_generated_catalog(
            registry.path(),
            "openrouter",
            OPENROUTER_MODELS_URL,
            &[entry],
            25,
            None,
        )
        .unwrap();
        assert_eq!(written, generated);
        assert_eq!(
            std::fs::read_to_string(manual).unwrap(),
            "models: [manual]\n"
        );
        let generated_text = std::fs::read_to_string(generated).unwrap();
        let document: Value = serde_yaml::from_str(&generated_text).unwrap();
        assert_eq!(document["provenance"]["provider"], "openrouter");
        assert_eq!(document["provenance"]["count"], 1);
        assert_eq!(document["provenance"]["cli_args"]["limit"], 25);
        assert_eq!(document["models"][0]["model_id"], "vendor/sample");
        assert!(document["models"][0]["input_price_per_million"]
            .as_f64()
            .is_some());
        assert!(!generated_text.contains("$serde_json::private::Number"));
    }
}
