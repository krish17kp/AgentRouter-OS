use std::{env, net::SocketAddr, path::PathBuf};

use agentrouter_api::server;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    std::panic::set_hook(Box::new(|_| {
        eprintln!("api.panic: request handler panicked; details withheld from logs");
    }));
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

    let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()?;
    runtime.block_on(async move {
        let listener = tokio::net::TcpListener::bind(&bind).await?;
        let address = listener.local_addr()?;
        println!("LISTENING {address}");
        let app = server::router(home).into_make_service_with_connect_info::<SocketAddr>();
        axum::serve(listener, app)
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await?;
        Ok::<(), Box<dyn std::error::Error>>(())
    })
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
