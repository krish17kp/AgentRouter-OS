use std::io::{self, Read};

use agentrouter_cli::limits::{client_key, CachedResponse, IdempotencyCache, RateLimiter};
use serde_json::{json, Value};

fn required_str<'a>(value: &'a Value, field: &str) -> Result<&'a str, String> {
    value[field]
        .as_str()
        .ok_or_else(|| format!("missing string field {field}"))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let output = match request["operation"].as_str() {
        Some("client_key") => json!({
            "key": client_key(request["api_key"].as_str(), request["host"].as_str())
        }),
        Some("rate") => {
            let limit = request["limit"].as_i64().map(i128::from);
            let window = request["window"].as_i64().map(i128::from);
            let limiter = RateLimiter::new(limit, window);
            let mut results = Vec::new();
            for hit in request["hits"].as_array().ok_or("hits must be an array")? {
                let key = required_str(hit, "key")?;
                let now = hit["now"].as_f64().ok_or("hit.now must be numeric")?;
                let (allowed, retry_after) = limiter.check_at(key, now);
                results.push(json!({"allowed": allowed, "retry_after": retry_after}));
            }
            json!({"results": results})
        }
        Some("cache") => {
            let ttl = request["ttl"].as_i64().map(i128::from);
            let cache = IdempotencyCache::new(ttl);
            let mut results = Vec::new();
            for action in request["actions"]
                .as_array()
                .ok_or("actions must be an array")?
            {
                let key = required_str(action, "key")?;
                let now = action["now"].as_f64().ok_or("action.now must be numeric")?;
                match action["action"].as_str() {
                    Some("put") => {
                        let response = &action["response"];
                        let status = response["status"]
                            .as_u64()
                            .ok_or("status must be unsigned")?;
                        let body = required_str(response, "body")?;
                        let media_type = response["media_type"].as_str().map(str::to_owned);
                        cache.put_at(
                            key,
                            CachedResponse {
                                status: u16::try_from(status)?,
                                body: body.as_bytes().to_vec(),
                                media_type,
                            },
                            now,
                        );
                        results.push(json!({"cached": true}));
                    }
                    Some("get") => {
                        let response = cache.get_at(key, now).map(|response| {
                            json!({
                                "status": response.status,
                                "body": String::from_utf8_lossy(&response.body),
                                "media_type": response.media_type,
                            })
                        });
                        results.push(json!({"response": response}));
                    }
                    _ => return Err("unknown cache action".into()),
                }
            }
            json!({"results": results})
        }
        _ => return Err("unknown operation".into()),
    };
    println!("{}", serde_json::to_string(&output)?);
    Ok(())
}
