use std::io::{self, Read};
use std::path::PathBuf;
use std::sync::Arc;

use agentrouter_reliability::{LoadOutcome, LoadSpec, Request, SoakResult};
use serde_json::{json, Value};

fn count_or_zero(request: &Value, key: &str) -> Result<usize, Box<dyn std::error::Error>> {
    let value = request
        .get(key)
        .ok_or_else(|| format!("{key} must be an integer"))?;
    if let Some(value) = value.as_i64() {
        return Ok(value.max(0) as usize);
    }
    if let Some(value) = value.as_u64() {
        return usize::try_from(value).map_err(|_| format!("{key} is too large").into());
    }
    Err(format!("{key} must be an integer").into())
}

fn run(request: &Value) -> Result<Value, Box<dyn std::error::Error>> {
    let operation = request
        .get("operation")
        .and_then(Value::as_str)
        .ok_or("operation must be a string")?;
    let value = match operation {
        "summarize_load" => {
            serde_json::from_value::<LoadOutcome>(request["outcome"].clone())?.as_dict()
        }
        "summarize_soak" => {
            serde_json::from_value::<SoakResult>(request["result"].clone())?.as_dict()
        }
        "package_exports" => {
            let _: fn(&str, &LoadSpec) -> LoadOutcome = agentrouter_reliability::run_load;
            let _: fn(PathBuf) -> Result<agentrouter_reliability::RunningApp, String> =
                agentrouter_reliability::serve_app;
            json!(agentrouter_reliability::PYTHON_PACKAGE_EXPORTS)
        }
        "run_load" => {
            let url = request
                .get("url")
                .and_then(Value::as_str)
                .ok_or("url must be a string")?;
            let total = count_or_zero(request, "total")?;
            let workers = count_or_zero(request, "workers")?;
            let timeout_seconds = request
                .get("timeout_seconds")
                .and_then(Value::as_f64)
                .unwrap_or(30.0);
            let custom_request = request.get("request").map(|value| {
                let method = value
                    .get("method")
                    .and_then(Value::as_str)
                    .unwrap_or("GET")
                    .to_string();
                let path = value
                    .get("path")
                    .and_then(Value::as_str)
                    .unwrap_or("/health")
                    .to_string();
                let body = value.get("body").filter(|value| !value.is_null()).cloned();
                Arc::new(move |_index| Request {
                    method: method.clone(),
                    path: path.clone(),
                    body: body.clone(),
                }) as agentrouter_reliability::RequestFactory
            });
            let outcome = agentrouter_reliability::run_load(
                url,
                &LoadSpec {
                    total,
                    workers,
                    timeout_seconds,
                    request: custom_request,
                },
            );
            outcome.as_dict()
        }
        "serve_and_load" => {
            let home = request
                .get("home")
                .and_then(Value::as_str)
                .ok_or("home must be a path")?;
            let total = count_or_zero(request, "total")?;
            let workers = count_or_zero(request, "workers")?;
            let timeout_seconds = request
                .get("timeout_seconds")
                .and_then(Value::as_f64)
                .unwrap_or(30.0);
            let mut app = agentrouter_reliability::serve_app(PathBuf::from(home))?;
            let outcome = agentrouter_reliability::run_load(
                &app.url,
                &LoadSpec {
                    total,
                    workers,
                    timeout_seconds,
                    request: Some(Arc::new(|_| Request::get("/health"))),
                },
            );
            app.stop()?;
            outcome.as_dict()
        }
        "soak" => {
            let url = request
                .get("url")
                .and_then(Value::as_str)
                .ok_or("url must be a string")?;
            let home = request
                .get("home")
                .and_then(Value::as_str)
                .ok_or("home must be a path")?;
            let seconds = request
                .get("seconds")
                .and_then(Value::as_f64)
                .unwrap_or(60.0);
            let workers = request
                .get("workers")
                .and_then(Value::as_u64)
                .and_then(|value| usize::try_from(value).ok())
                .unwrap_or(8);
            let batch = request
                .get("batch")
                .and_then(Value::as_u64)
                .and_then(|value| usize::try_from(value).ok())
                .unwrap_or(50);
            agentrouter_reliability::soak(url, &PathBuf::from(home), seconds, workers, batch)
                .as_dict()
        }
        _ => return Err(format!("unknown operation '{operation}'").into()),
    };
    Ok(json!({"value": value}))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    println!("{}", serde_json::to_string(&run(&request)?)?);
    Ok(())
}
