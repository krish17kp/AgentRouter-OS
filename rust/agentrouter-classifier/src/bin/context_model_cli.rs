use std::io::{self, Read};

use agentrouter_classifier::context_model::{feature_vector, load_model};
use serde_json::json;

fn main() {
    let mut prompt = String::new();
    if io::stdin().read_to_string(&mut prompt).is_err() || prompt.is_empty() {
        eprintln!("usage: context_model_cli < prompt");
        std::process::exit(2);
    }
    let Some(model) = load_model() else {
        eprintln!("context-band model is absent or invalid");
        std::process::exit(1);
    };
    println!(
        "{}",
        json!({
            "features": feature_vector(&prompt),
            "prediction": model.predict(&prompt),
        })
    );
}
