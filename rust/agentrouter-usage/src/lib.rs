//! Rust port of `agentrouter/usage.py`'s state machine —
//! UNKNOWN/UNSUPPORTED/AVAILABLE/EXHAUSTED/ERROR quota intelligence.
//! `apply_live_verification` (the re-ranking glue into `engine.route()`'s
//! dict-shaped result) is deliberately NOT ported here: it is CLI/route
//! presentation glue over dynamically-shaped dicts, not part of the state
//! machine the port-plan's acceptance criterion names, and `agentrouter
//! -routing`'s `RouteResult` is a typed struct rather than a dict, so the
//! re-ranking call site belongs with the CLI/API port (R4/R5), not here.
//!
//! No live adapter is registered in production in either language today
//! (`agentrouter/usage.py`'s own `_LIVE_CHECKS` is empty — BACKLOG.yaml P2,
//! credential-gated) — `register_live_check` exists only so a future
//! adapter or a test double can prove the mechanism end-to-end.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;

pub const UNKNOWN: &str = "unknown";
pub const UNSUPPORTED: &str = "unsupported";
pub const AVAILABLE: &str = "available";
pub const EXHAUSTED: &str = "exhausted";
pub const ERROR: &str = "error";

fn is_known_state(s: &str) -> bool {
    matches!(s, UNKNOWN | UNSUPPORTED | AVAILABLE | EXHAUSTED | ERROR)
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct UsageStatus {
    pub provider: String,
    pub state: String,
    pub detail: String,
    pub remaining: Option<f64>,
    pub reset_at: Option<String>,
    pub checked_at: Option<f64>,
    pub source: String,
}

impl UsageStatus {
    pub fn new(provider: &str, state: &str, detail: &str) -> Self {
        UsageStatus {
            provider: provider.to_string(),
            state: state.to_string(),
            detail: detail.to_string(),
            remaining: None,
            reset_at: None,
            checked_at: None,
            source: "none".to_string(),
        }
    }
}

/// Strip control characters from adapter-supplied text, same defense as
/// Python's `usage._sanitize` / `hosts._sanitize`.
fn sanitize(value: &str) -> String {
    value
        .chars()
        .filter(|c| !c.is_control())
        .take(200)
        .collect()
}

fn now_epoch_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

type LiveCheckFn = std::sync::Arc<dyn Fn(f64) -> UsageStatus + Send + Sync + 'static>;

fn live_checks() -> &'static Mutex<HashMap<String, LiveCheckFn>> {
    static CELL: OnceLock<Mutex<HashMap<String, LiveCheckFn>>> = OnceLock::new();
    CELL.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Extension hook for a future adapter (or a test double). Not called in
/// production.
pub fn register_live_check(
    provider: &str,
    fn_: impl Fn(f64) -> UsageStatus + Send + Sync + 'static,
) {
    live_checks()
        .lock()
        .unwrap()
        .insert(provider.to_string(), std::sync::Arc::new(fn_));
}

/// Test-only teardown counterpart to [`register_live_check`].
pub fn unregister_live_check(provider: &str) {
    live_checks().lock().unwrap().remove(provider);
}

/// Quota state for one provider. Never panics across the boundary; never
/// invents a number. Mirrors `usage.check_usage`.
pub fn check_usage(provider: &str, live: bool, timeout: Duration) -> UsageStatus {
    if !live {
        return UsageStatus::new(provider, UNKNOWN, "live verification not requested");
    }

    let fn_ = live_checks().lock().unwrap().get(provider).cloned();
    let Some(fn_) = fn_ else {
        return UsageStatus::new(
            provider,
            UNSUPPORTED,
            &format!("no live usage check registered for '{provider}'"),
        );
    };

    // Run the adapter on its own thread and enforce a real wall-clock bound
    // here, exactly as Python's `ThreadPoolExecutor` + `wait()` does: one
    // misbehaving adapter can never hang the caller past `timeout`, and a
    // panic inside the adapter is caught and reported as our ERROR rather
    // than propagating. The registry lock is released before this call (we
    // already cloned the `Arc` out above), so a panicking adapter can never
    // poison the shared registry for other providers/tests.
    let timeout_secs = timeout.as_secs_f64();
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| fn_(timeout_secs)));
        let _ = tx.send(result);
    });

    match rx.recv_timeout(timeout) {
        Err(_) => UsageStatus {
            provider: provider.to_string(),
            state: ERROR.to_string(),
            detail: format!("live check exceeded the {timeout_secs}s timeout"),
            remaining: None,
            reset_at: None,
            checked_at: Some(now_epoch_secs()),
            source: "live".to_string(),
        },
        Ok(Err(_panic)) => UsageStatus {
            provider: provider.to_string(),
            state: ERROR.to_string(),
            detail: "live check failed (panic)".to_string(),
            remaining: None,
            reset_at: None,
            checked_at: Some(now_epoch_secs()),
            source: "live".to_string(),
        },
        Ok(Ok(status)) => {
            if !is_known_state(&status.state) {
                return UsageStatus {
                    provider: provider.to_string(),
                    state: ERROR.to_string(),
                    detail: "live check returned an unrecognized result".to_string(),
                    remaining: None,
                    reset_at: None,
                    checked_at: Some(now_epoch_secs()),
                    source: "live".to_string(),
                };
            }
            UsageStatus {
                provider: status.provider,
                state: status.state,
                detail: sanitize(&status.detail),
                remaining: status.remaining,
                reset_at: status.reset_at,
                checked_at: status.checked_at,
                source: status.source,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn not_live_is_unknown() {
        let s = check_usage("anthropic", false, Duration::from_secs(5));
        assert_eq!(s.state, UNKNOWN);
        assert_eq!(s.source, "none");
    }

    #[test]
    fn live_without_registered_adapter_is_unsupported() {
        let s = check_usage("no-such-provider", true, Duration::from_secs(5));
        assert_eq!(s.state, UNSUPPORTED);
    }

    #[test]
    fn registered_adapter_reports_its_state() {
        register_live_check("fake", |_timeout| UsageStatus {
            provider: "fake".to_string(),
            state: AVAILABLE.to_string(),
            detail: "plenty left".to_string(),
            remaining: Some(42.0),
            reset_at: None,
            checked_at: Some(123.0),
            source: "live".to_string(),
        });
        let s = check_usage("fake", true, Duration::from_secs(5));
        unregister_live_check("fake");
        assert_eq!(s.state, AVAILABLE);
        assert_eq!(s.remaining, Some(42.0));
        assert_eq!(s.source, "live");
    }

    #[test]
    fn slow_adapter_times_out_as_error() {
        register_live_check("slow", |_timeout| {
            std::thread::sleep(Duration::from_secs(2));
            UsageStatus::new("slow", AVAILABLE, "too late")
        });
        let s = check_usage("slow", true, Duration::from_millis(50));
        unregister_live_check("slow");
        assert_eq!(s.state, ERROR);
        assert!(s.detail.contains("timeout"));
    }

    #[test]
    fn panicking_adapter_is_reported_as_error_not_propagated() {
        register_live_check("panics", |_timeout| panic!("boom"));
        let s = check_usage("panics", true, Duration::from_secs(5));
        unregister_live_check("panics");
        assert_eq!(s.state, ERROR);
    }
}
