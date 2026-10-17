//! Takes the task text as a single CLI argument and prints the resulting
//! `Classification` as JSON on stdout. Exists purely so
//! `tests/test_classifier_rust_compat.py` can diff Rust output against
//! Python's `agentrouter.classifier.classify()` for the same prompt.

use agentrouter_classifier::{classify, ClassifyOptions};

fn main() {
    let task = std::env::args()
        .nth(1)
        .expect("usage: classify_cli <task text>");
    let classification = classify(&task, &ClassifyOptions::default());
    println!("{}", serde_json::to_string(&classification).unwrap());
}
