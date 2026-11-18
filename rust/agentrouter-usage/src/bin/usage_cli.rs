//! Takes `<provider> <live:true|false>` and prints `check_usage`'s
//! `UsageStatus` as JSON. No live adapter is ever registered here, so this
//! is deterministic — exists purely so `tests/test_usage_rust_compat.py`
//! can diff it against Python's `usage.check_usage()` for the same inputs.

use std::time::Duration;

use agentrouter_usage::check_usage;

fn main() {
    let mut args = std::env::args().skip(1);
    let provider = args
        .next()
        .expect("usage: usage_cli <provider> <live:true|false>");
    let live: bool = args
        .next()
        .expect("usage: usage_cli <provider> <live:true|false>")
        .parse()
        .expect("live must be true or false");
    let status = check_usage(&provider, live, Duration::from_secs(5));
    println!("{}", serde_json::to_string(&status).unwrap());
}
