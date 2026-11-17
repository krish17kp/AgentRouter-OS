use std::{env, path::PathBuf};

use agentrouter_api::server;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bind = "127.0.0.1:8787".to_string();
    let mut home = agentrouter_api::service::home();
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
