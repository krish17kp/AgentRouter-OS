//! Offline generated-catalog and override parity probe.
use agentrouter_registry::{load_all_models, load_providers};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    providers_yaml: String,
    manual_yaml: String,
    generated: Vec<(String, String)>,
    overrides_yaml: Option<String>,
    today: String,
}

#[derive(Serialize)]
struct Response {
    keys: Vec<String>,
    abilities: Vec<(u8, u8, u8)>,
    warnings: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let providers = load_providers(&request.providers_yaml)?;
    let today = NaiveDate::parse_from_str(&request.today, "%Y-%m-%d")?;
    let (models, warnings) = load_all_models(
        &request.manual_yaml,
        &request.generated,
        request.overrides_yaml.as_deref(),
        &providers,
        today,
    )?;
    let response = Response {
        keys: models.iter().map(|model| model.key()).collect(),
        abilities: models
            .iter()
            .map(|m| (m.ability.coding, m.ability.reasoning, m.ability.writing))
            .collect(),
        warnings,
    };
    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}
