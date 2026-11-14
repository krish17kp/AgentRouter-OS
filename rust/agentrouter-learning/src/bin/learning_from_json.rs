//! Offline Python/Rust fixture probe for `agentrouter.learning.learned_weights`.

use std::io::{self, Read};

use agentrouter_routing::Weights;
use rusqlite::Connection;
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    weights: WeightsInput,
    ratings: Vec<Option<i64>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct WeightsInput {
    w_cap: f64,
    w_cost: f64,
    w_lat: f64,
    w_ctx: f64,
}

impl From<WeightsInput> for Weights {
    fn from(value: WeightsInput) -> Self {
        Self {
            w_cap: value.w_cap,
            w_cost: value.w_cost,
            w_lat: value.w_lat,
            w_ctx: value.w_ctx,
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let conn = Connection::open_in_memory()?;
    conn.execute_batch("CREATE TABLE feedback (rating INTEGER);")?;
    for rating in request.ratings {
        conn.execute("INSERT INTO feedback (rating) VALUES (?1)", [rating])?;
    }
    let (weights, note) = agentrouter_learning::learned_weights(&conn, &request.weights.into())?;
    println!(
        "{}",
        json!({
            "weights": {
                "w_cap": weights.w_cap,
                "w_cost": weights.w_cost,
                "w_lat": weights.w_lat,
                "w_ctx": weights.w_ctx,
            },
            "note": note,
        })
    );
    Ok(())
}
