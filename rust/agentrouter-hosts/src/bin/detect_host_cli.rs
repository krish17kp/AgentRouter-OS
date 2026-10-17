//! Takes `<host> [required_command]` and prints the resulting `HostStatus`
//! as JSON. Exists purely so `tests/test_hosts_rust_compat.py` can diff
//! Rust output against Python's `hosts.detect_host()` under the same
//! controlled environment (the test sets env vars / `AGENTROUTER_HOME`
//! identically for both processes).

use agentrouter_hosts::detect_host;

fn main() {
    let mut args = std::env::args().skip(1);
    let host = args
        .next()
        .expect("usage: detect_host_cli <host> [required_command]");
    let required_command = args.next();
    let status = detect_host(&host, required_command.as_deref());
    println!("{}", serde_json::to_string(&status).unwrap());
}
