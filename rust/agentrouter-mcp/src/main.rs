use std::{env, path::PathBuf};

use agentrouter_mcp::{run_stdio, Server};

fn main() {
    let home = match home_dir() {
        Ok(home) => home,
        Err(message) => {
            eprintln!("agentrouter-mcp-server: {message}");
            std::process::exit(2);
        }
    };
    if let Err(error) = run_stdio(&Server::new(home)) {
        eprintln!("agentrouter-mcp-server: {error}");
        std::process::exit(1);
    }
}

fn home_dir() -> Result<PathBuf, String> {
    let mut args = env::args().skip(1);
    let mut home = env::var_os("AGENTROUTER_HOME").map(PathBuf::from);
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--home" => {
                let value = args.next().ok_or("--home requires a path")?;
                home = Some(PathBuf::from(value));
            }
            "--help" | "-h" => {
                println!("Usage: agentrouter-mcp-server [--home PATH]");
                std::process::exit(0);
            }
            other => return Err(format!("unknown argument {other}")),
        }
    }
    if let Some(home) = home {
        return Ok(home);
    }
    let home = env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .ok_or("set AGENTROUTER_HOME or pass --home PATH")?;
    Ok(home.join(".agentrouter"))
}
