//! Rust port of `agentrouter/usage.py`'s quota state machine and one-step
//! exhaustion reranking. The deterministic status seam and route result
//! preserve the Python contract while allowing offline differential tests.
//!
//! No live adapter is registered in production in either language today
//! (`agentrouter/usage.py`'s own `_LIVE_CHECKS` is empty — BACKLOG.yaml P2,
//! credential-gated) — `register_live_check` exists only so a future
//! adapter or a test double can prove the mechanism end-to-end.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use agentrouter_core::Classification;
use agentrouter_registry::ModelEntry;
use agentrouter_routing::{route, RouteResult, Weights};
use serde::{Deserialize, Serialize};
use unicode_general_category::{get_general_category, GeneralCategory};

pub const UNKNOWN: &str = "unknown";
pub const UNSUPPORTED: &str = "unsupported";
pub const AVAILABLE: &str = "available";
pub const EXHAUSTED: &str = "exhausted";
pub const ERROR: &str = "error";

fn is_known_state(s: &str) -> bool {
    matches!(s, UNKNOWN | UNSUPPORTED | AVAILABLE | EXHAUSTED | ERROR)
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UsageStatus {
    pub provider: String,
    pub state: String,
    pub detail: String,
    pub remaining: Option<f64>,
    pub reset_at: Option<String>,
    pub checked_at: Option<f64>,
    pub source: String,
}

/// Route fields plus the live quota evidence, flattened to match Python's
/// `apply_live_verification` dictionary contract.
#[derive(Debug, Clone, Serialize)]
pub struct UsageRouteResult {
    #[serde(flatten)]
    pub route: RouteResult,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage_check: Option<UsageStatus>,
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

/// Replace non-printable characters in adapter text, matching Python's
/// `str.isprintable()` behavior in `usage._sanitize` / `hosts._sanitize`.
fn is_printable(character: char) -> bool {
    match get_general_category(character) {
        GeneralCategory::Control
        | GeneralCategory::Format
        | GeneralCategory::Surrogate
        | GeneralCategory::PrivateUse
        | GeneralCategory::Unassigned
        | GeneralCategory::LineSeparator
        | GeneralCategory::ParagraphSeparator => false,
        GeneralCategory::SpaceSeparator => character == ' ',
        _ => true,
    }
}

fn sanitize(value: &str) -> String {
    value
        .chars()
        .map(|c| if is_printable(c) { c } else { '?' })
        .take(200)
        .collect()
}

fn now_epoch_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

fn normalize_adapter_status(status: UsageStatus) -> UsageStatus {
    if !is_known_state(&status.state) {
        return UsageStatus {
            provider: status.provider,
            state: ERROR.to_string(),
            detail: "live check returned an unrecognized result".to_string(),
            remaining: None,
            reset_at: None,
            checked_at: Some(now_epoch_secs()),
            source: "live".to_string(),
        };
    }
    UsageStatus {
        detail: sanitize(&status.detail),
        ..status
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LiveCheckError {
    pub exception_type: String,
}

impl LiveCheckError {
    pub fn new(exception_type: impl Into<String>) -> Self {
        Self {
            exception_type: exception_type.into(),
        }
    }
}

type LiveCheckFn =
    std::sync::Arc<dyn Fn(f64) -> Result<UsageStatus, LiveCheckError> + Send + Sync + 'static>;

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
    register_live_check_result(provider, move |timeout| Ok(fn_(timeout)));
}

/// Register a check that can preserve the source exception class in its
/// bounded failure result, matching Python's `type(exc).__name__` contract.
pub fn register_live_check_result(
    provider: &str,
    fn_: impl Fn(f64) -> Result<UsageStatus, LiveCheckError> + Send + Sync + 'static,
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
        Ok(Ok(Err(error))) => UsageStatus {
            provider: provider.to_string(),
            state: ERROR.to_string(),
            detail: format!("live check failed ({})", error.exception_type),
            remaining: None,
            reset_at: None,
            checked_at: Some(now_epoch_secs()),
            source: "live".to_string(),
        },
        Ok(Ok(Ok(status))) => normalize_adapter_status(status),
    }
}

/// If the recommended provider is verified exhausted, rerank once without its
/// top model. Mirrors `usage.apply_live_verification`; unverified and
/// unsupported quota states never alter the route.
pub fn apply_live_verification(
    models: &[ModelEntry],
    cls: &Classification,
    result: RouteResult,
    base_weights: Weights,
    prefer: Option<&str>,
    timeout: Duration,
) -> UsageRouteResult {
    let Some(recommended) = result.recommendation.as_ref() else {
        return UsageRouteResult {
            route: result,
            usage_check: None,
        };
    };
    let top_provider = recommended.provider.clone();
    let status = check_usage(&top_provider, true, timeout);
    apply_usage_status(models, cls, result, status, base_weights, prefer)
}

/// Apply an already collected live status to a route. This is also the
/// deterministic seam used by offline contract tests; it makes no network
/// calls and follows the same one-rerank policy as Python.
pub fn apply_usage_status(
    models: &[ModelEntry],
    cls: &Classification,
    result: RouteResult,
    status: UsageStatus,
    base_weights: Weights,
    prefer: Option<&str>,
) -> UsageRouteResult {
    let Some(recommended) = result.recommendation.as_ref() else {
        return UsageRouteResult {
            route: result,
            usage_check: None,
        };
    };
    let status = normalize_adapter_status(status);
    let top_key = recommended.model.clone();
    if status.state != EXHAUSTED {
        return UsageRouteResult {
            route: result,
            usage_check: Some(status),
        };
    }

    let Some(top_model) = models.iter().find(|model| model.key() == top_key) else {
        return UsageRouteResult {
            route: result,
            usage_check: Some(status),
        };
    };
    let remaining = models
        .iter()
        .filter(|model| model.key() != top_key)
        .cloned()
        .collect::<Vec<_>>();
    let mut retry = route(&remaining, cls, base_weights, prefer);
    retry.excluded = vec![agentrouter_routing::Excluded {
        model: top_key.clone(),
        reason: format!("quota exhausted (live-verified): {}", status.detail),
    }];
    retry.excluded.extend(result.excluded.clone());
    retry.weight_shifts = result.weight_shifts.clone();
    retry.weight_shifts.push(format!(
        "quota exhausted for {}; re-ranked excluding {}",
        top_model.provider.as_str(),
        top_key
    ));
    UsageRouteResult {
        route: retry,
        usage_check: Some(status),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use agentrouter_core::{ApprovalLevel, ContextBand, Level, OutputType, TaskType};
    use agentrouter_routing::Weights;

    fn model(provider: &str, model_id: &str) -> ModelEntry {
        let yaml = format!(
            "provider: {provider}\nmodel_id: {model_id}\ncontext_window: 100000\nmax_output_tokens: 8000\npricing_tier: medium\nlatency_tier: medium\nability: {{coding: 7, reasoning: 7, writing: 7}}\ntool_support: []\nvision_support: false\ndeprecation_status: active\n"
        );
        serde_yaml::from_str(&yaml).unwrap()
    }

    fn classification() -> Classification {
        Classification {
            task_type: TaskType::Coding,
            complexity: Level::Medium,
            risk: Level::Low,
            context_tokens: 0.into(),
            context_band: ContextBand::Small,
            output_type: OutputType::Code,
            tool_needs: vec![],
            approval_level: ApprovalLevel::Auto,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        }
    }

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
        assert_eq!(s.detail, "live check failed (panic)");
    }

    #[test]
    fn typed_adapter_error_preserves_the_python_exception_class() {
        register_live_check_result("typed-error", |_timeout| {
            Err(LiveCheckError::new("TimeoutError"))
        });
        let status = check_usage("typed-error", true, Duration::from_secs(5));
        unregister_live_check("typed-error");
        assert_eq!(status.state, ERROR);
        assert_eq!(status.detail, "live check failed (TimeoutError)");
        assert_eq!(status.source, "live");
        assert!(status.checked_at.is_some());
    }

    #[test]
    fn exhausted_recommendation_is_reranked_once_and_annotated() {
        let models = vec![model("quota-openai", "first"), model("other", "second")];
        let cls = classification();
        let original = route(&models, &cls, Weights::default(), None);
        let first = original.recommendation.as_ref().unwrap().model.clone();
        register_live_check("quota-openai", |_timeout| {
            let mut status = UsageStatus::new("quota-openai", EXHAUSTED, "no budget left");
            status.remaining = Some(0.0);
            status.source = "live".to_string();
            status
        });
        let result = apply_live_verification(
            &models,
            &cls,
            original.clone(),
            Weights::default(),
            None,
            Duration::from_secs(1),
        );
        unregister_live_check("quota-openai");

        assert_ne!(result.route.recommendation.as_ref().unwrap().model, first);
        assert_eq!(result.usage_check.as_ref().unwrap().state, EXHAUSTED);
        assert!(result.route.excluded[0].reason.contains("quota exhausted"));
        assert!(result
            .route
            .weight_shifts
            .last()
            .unwrap()
            .contains("quota exhausted"));
        assert_eq!(original.recommendation.unwrap().model, first);
    }

    #[test]
    fn unsupported_usage_preserves_recommendation_and_no_pick_has_no_usage_field() {
        let models = vec![model("unsupported-provider", "first")];
        let cls = classification();
        let original = route(&models, &cls, Weights::default(), None);
        let result = apply_live_verification(
            &models,
            &cls,
            original.clone(),
            Weights::default(),
            None,
            Duration::from_secs(1),
        );
        assert_eq!(
            result.route.recommendation.unwrap().model,
            original.recommendation.unwrap().model
        );
        assert_eq!(result.usage_check.unwrap().state, UNSUPPORTED);

        let empty = route(&[], &cls, Weights::default(), None);
        let result = apply_live_verification(
            &[],
            &cls,
            empty,
            Weights::default(),
            None,
            Duration::from_secs(1),
        );
        assert!(result.usage_check.is_none());
        assert!(serde_json::to_value(result)
            .unwrap()
            .get("usage_check")
            .is_none());
    }

    #[test]
    fn unknown_adapter_state_fails_closed_without_reranking() {
        let models = vec![model("provider", "model")];
        let cls = classification();
        let original = route(&models, &cls, Weights::default(), None);
        let recommendation = original.recommendation.as_ref().unwrap().model.clone();
        let result = apply_usage_status(
            &models,
            &cls,
            original,
            UsageStatus::new("provider", "future-state", "ignored"),
            Weights::default(),
            None,
        );
        assert_eq!(result.usage_check.unwrap().state, ERROR);
        assert_eq!(result.route.recommendation.unwrap().model, recommendation);
    }
}
