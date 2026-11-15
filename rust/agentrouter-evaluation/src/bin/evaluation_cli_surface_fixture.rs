//! Test-only process fixture for installed CLI discovery failure contracts.

fn main() {
    match std::env::var("AGENTROUTER_TEST_SURFACE_MODE").as_deref() {
        Ok("nonzero") => std::process::exit(7),
        Ok("malformed") => println!("not-json"),
        Ok("unknown-field") => {
            println!("{{\"commands\":[],\"groups\":[],\"unexpected\":true}}")
        }
        _ => println!("{{\"commands\":[],\"groups\":[]}}"),
    }
}
