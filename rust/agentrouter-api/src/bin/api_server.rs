use std::{env, path::PathBuf};

use agentrouter_api::server;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bind = "127.0.0.1:8787".to_string();
    let mut home = default_home();
    let mut args = env::args().skip(1);
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--bind" => bind = args.next().ok_or("--bind requires an address")?,
            "--home" => home = PathBuf::from(args.next().ok_or("--home requires a path")?),
            "--help" | "-h" => {
                println!("Usage: agentrouter-api-server [--bind HOST:PORT] [--home PATH]");
                return Ok(());
            }
            _ => return Err(format!("unknown argument: {argument}").into()),
        }
    }

    server::run(bind, home)
}

fn default_home() -> PathBuf {
    if let Some(home) = env::var_os("AGENTROUTER_HOME") {
        return PathBuf::from(home);
    }
    let base = if cfg!(windows) {
        env::var_os("USERPROFILE")
    } else {
        env::var_os("HOME")
    }
    .map(PathBuf::from)
    .unwrap_or_else(|| PathBuf::from("."));
    base.join(".agentrouter")
}
