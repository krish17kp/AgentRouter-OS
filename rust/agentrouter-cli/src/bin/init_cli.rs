//! Compatibility probe for `agentrouter init` without `--force`.
//!
//! Usage: init_cli <home>

use std::path::PathBuf;

fn main() {
    let home = PathBuf::from(std::env::args().nth(1).expect("usage: init_cli <home>"));
    match agentrouter_cli::init_home(&home) {
        Ok(lines) => {
            for line in lines {
                println!("{line}");
            }
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(3);
        }
    }
}
