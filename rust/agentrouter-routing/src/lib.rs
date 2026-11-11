//! Rust port of `agentrouter/engine.py` — eligibility filters, scoring,
//! fallback selection (ROUTING_RULES.md §2-5). Field-for-field with the
//! Python module; see `tests/test_routing_rust_compat.py` for the
//! byte-for-byte check against `agentrouter/benchmarks/routing_gold_v1.yaml`.

use std::collections::{HashMap, HashSet};

use agentrouter_core::{Classification, ContextBand, Level, PricingTier, TaskType};
use agentrouter_policy::taxonomy;
use agentrouter_registry::{DeprecationStatus, LatencyTier, ModelEntry};
use serde::Serialize;

/// capability blend per task_type (ROUTING_RULES.md §3)
fn cap_blend(task_type: TaskType) -> &'static [(&'static str, f64)] {
    match task_type {
        TaskType::Coding => &[("coding", 1.0)],
        TaskType::Reasoning => &[("reasoning", 1.0)],
        TaskType::Writing => &[("writing", 1.0)],
        TaskType::Analysis => &[("reasoning", 0.7), ("writing", 0.3)],
        TaskType::Summarization => &[("writing", 0.7), ("reasoning", 0.3)],
        TaskType::General => &[
            ("coding", 1.0 / 3.0),
            ("reasoning", 1.0 / 3.0),
            ("writing", 1.0 / 3.0),
        ],
    }
}

fn cost_fit(complexity: Level, tier: PricingTier) -> f64 {
    match (complexity, tier) {
        (Level::Low, PricingTier::Free) => 1.0,
        (Level::Low, PricingTier::Low) => 0.9,
        (Level::Low, PricingTier::Medium) => 0.6,
        (Level::Low, PricingTier::High) => 0.3,
        (Level::Low, PricingTier::Frontier) => 0.1,
        (Level::Medium, PricingTier::Free) => 0.7,
        (Level::Medium, PricingTier::Low) => 0.8,
        (Level::Medium, PricingTier::Medium) => 1.0,
        (Level::Medium, PricingTier::High) => 0.8,
        (Level::Medium, PricingTier::Frontier) => 0.6,
        (Level::High, PricingTier::Free) => 0.4,
        (Level::High, PricingTier::Low) => 0.5,
        (Level::High, PricingTier::Medium) => 0.7,
        (Level::High, PricingTier::High) => 0.9,
        (Level::High, PricingTier::Frontier) => 1.0,
    }
}

fn lat_fit(complexity: Level, tier: LatencyTier) -> f64 {
    match (complexity, tier) {
        (Level::Low, LatencyTier::Fast) => 1.0,
        (Level::Low, LatencyTier::Medium) => 0.7,
        (Level::Low, LatencyTier::Slow) => 0.3,
        (Level::Medium, LatencyTier::Fast) => 0.9,
        (Level::Medium, LatencyTier::Medium) => 0.8,
        (Level::Medium, LatencyTier::Slow) => 0.5,
        (Level::High, LatencyTier::Fast) => 0.8,
        (Level::High, LatencyTier::Medium) => 0.8,
        (Level::High, LatencyTier::Slow) => 0.6,
    }
}

const DEPRECATION_PENALTY: f64 = 0.2;
const IDEAL_BOOST: f64 = 0.05;
const AVOID_PENALTY: f64 = 0.10;

/// `list(PricingTier)` declaration order in `schema.py` (free < low < medium
/// < high < frontier) — used for `pick_fallback`'s "lower pricing tier"
/// comparison exactly as Python's `tiers.index(...)` does.
fn pricing_tier_rank(t: PricingTier) -> u8 {
    match t {
        PricingTier::Free => 0,
        PricingTier::Low => 1,
        PricingTier::Medium => 2,
        PricingTier::High => 3,
        PricingTier::Frontier => 4,
    }
}

pub const BASE_W_CAP: f64 = 0.45;
pub const BASE_W_COST: f64 = 0.25;
pub const BASE_W_LAT: f64 = 0.15;
pub const BASE_W_CTX: f64 = 0.15;

#[derive(Debug, Clone, Copy)]
pub struct Weights {
    pub w_cap: f64,
    pub w_cost: f64,
    pub w_lat: f64,
    pub w_ctx: f64,
}

impl Default for Weights {
    fn default() -> Self {
        Weights {
            w_cap: BASE_W_CAP,
            w_cost: BASE_W_COST,
            w_lat: BASE_W_LAT,
            w_ctx: BASE_W_CTX,
        }
    }
}

impl Weights {
    fn as_map(&self) -> HashMap<&'static str, f64> {
        HashMap::from([
            ("w_cap", self.w_cap),
            ("w_cost", self.w_cost),
            ("w_lat", self.w_lat),
            ("w_ctx", self.w_ctx),
        ])
    }
}

/// Mirrors `engine.weights_for`. Returns (weights, shift-explanations).
pub fn weights_for(
    cls: &Classification,
    base: Weights,
    prefer: Option<&str>,
) -> (Weights, Vec<String>) {
    if let Some(name) = prefer {
        let table = agentrouter_policy::preference_weights();
        let w = table.get(name).expect("unknown preference name");
        return (
            Weights {
                w_cap: w["w_cap"],
                w_cost: w["w_cost"],
                w_lat: w["w_lat"],
                w_ctx: w["w_ctx"],
            },
            vec![format!("preference={} -> fixed weights", name)],
        );
    }
    let mut w = base;
    let mut shifts = Vec::new();
    if cls.complexity == Level::High || cls.risk == Level::High {
        w.w_cap = 0.55;
        w.w_cost = 0.15;
        shifts.push("complexity/risk=high -> w_cap 0.55, w_cost 0.15".to_string());
    } else if cls.complexity == Level::Low {
        w.w_cap = 0.35;
        w.w_cost = 0.35;
        shifts.push("complexity=low -> w_cap 0.35, w_cost 0.35".to_string());
    }
    if cls.context_band == ContextBand::Large {
        w.w_ctx = 0.25;
        w.w_lat = 0.05;
        shifts.push("context=large -> w_ctx 0.25, w_lat 0.05".to_string());
    }
    (w, shifts)
}

#[derive(Debug, Clone, Serialize)]
pub struct Excluded {
    pub model: String,
    pub reason: String,
}

fn task_type_value(t: TaskType) -> &'static str {
    match t {
        TaskType::Coding => "coding",
        TaskType::Reasoning => "reasoning",
        TaskType::Writing => "writing",
        TaskType::Analysis => "analysis",
        TaskType::Summarization => "summarization",
        TaskType::General => "general",
    }
}

/// Mirrors `engine.eligibility`: hard filters (ROUTING_RULES.md §2).
pub fn eligibility<'a>(
    models: &'a [ModelEntry],
    cls: &Classification,
) -> (Vec<&'a ModelEntry>, Vec<Excluded>) {
    let mut eligible = Vec::new();
    let mut excluded = Vec::new();
    for m in models {
        if m.deprecation_status == DeprecationStatus::Retired {
            excluded.push(Excluded {
                model: m.key(),
                reason: "retired".to_string(),
            });
            continue;
        }
        if m.context_window < cls.context_tokens {
            excluded.push(Excluded {
                model: m.key(),
                reason: format!("context {} < {}", m.context_window, cls.context_tokens),
            });
            continue;
        }
        let support: HashSet<String> = m.tool_support.iter().cloned().collect();
        let missing: Vec<&str> = cls
            .tool_needs
            .iter()
            .filter(|t| t.as_str() != "vision")
            .map(|t| t.as_str())
            .filter(|t| !taxonomy::satisfied_by(t, &support))
            .collect();
        if !missing.is_empty() {
            excluded.push(Excluded {
                model: m.key(),
                reason: format!("missing tools: {}", missing.join(",")),
            });
            continue;
        }
        if cls.tool_needs.iter().any(|t| t == "vision") && !m.vision_support {
            excluded.push(Excluded {
                model: m.key(),
                reason: "no vision support".to_string(),
            });
            continue;
        }
        eligible.push(m);
    }
    (eligible, excluded)
}

fn capability_match(m: &ModelEntry, task_type: TaskType) -> f64 {
    cap_blend(task_type)
        .iter()
        .map(|(dim, w)| {
            let v = match *dim {
                "coding" => m.ability.coding,
                "reasoning" => m.ability.reasoning,
                "writing" => m.ability.writing,
                _ => unreachable!(),
            };
            (v as f64 / 10.0) * w
        })
        .sum()
}

fn context_fit(m: &ModelEntry, cls: &Classification) -> f64 {
    let ratio = m.context_window as f64 / (cls.context_tokens.max(1) as f64);
    if ratio < 2.0 {
        0.7
    } else if ratio < 16.0 {
        1.0
    } else {
        0.6
    }
}

fn use_case_adjust(m: &ModelEntry, task_type: TaskType) -> f64 {
    let v = task_type_value(task_type);
    let mut adj = 0.0;
    if m.ideal_use_cases.iter().any(|u| u == v) {
        adj += IDEAL_BOOST;
    }
    if m.avoid_use_cases.iter().any(|u| u == v) {
        adj -= AVOID_PENALTY;
    }
    adj
}

/// Rounds like Python's `round()` (round-half-to-even) rather than Rust's
/// default round-half-away-from-zero — the two only diverge on exact
/// `.xx5` boundaries, but the engine's scores are built from eighths/tenths
/// where that can occur.
/// Mirrors Python's `round(x, ndigits)`: both resolve to a correctly-rounded
/// decimal conversion of the float's exact binary value with ties-to-even,
/// which is exactly what Rust's `{:.N}` float formatting does too — scaling
/// by `10^ndigits` first (the previous approach here) reintroduces binary
/// float error that can flip a case landing exactly on a `.5` boundary.
fn round_half_even(x: f64, ndigits: i32) -> f64 {
    let ndigits = ndigits.max(0) as usize;
    format!("{x:.ndigits$}").parse().unwrap()
}

#[derive(Debug, Clone, Serialize)]
pub struct Terms {
    pub cap: f64,
    pub cost: f64,
    pub lat: f64,
    pub ctx: f64,
    pub adj: f64,
    pub dep: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScoredModel {
    pub model: String,
    pub provider: String,
    pub model_id: String,
    pub pricing_tier: String,
    pub terms: Terms,
    pub score: f64,
}

/// Mirrors `engine.score_models`: score + rank eligible models, best-first.
pub fn score_models(
    eligible: &[&ModelEntry],
    cls: &Classification,
    weights: Weights,
) -> Vec<ScoredModel> {
    let mut rows: Vec<ScoredModel> = eligible
        .iter()
        .map(|m| {
            let cap = capability_match(m, cls.task_type);
            let cost = cost_fit(cls.complexity, m.pricing_tier);
            let lat = lat_fit(cls.complexity, m.latency_tier);
            let ctx = context_fit(m, cls);
            let adj = use_case_adjust(m, cls.task_type);
            let dep = if m.deprecation_status == DeprecationStatus::Deprecated {
                DEPRECATION_PENALTY
            } else {
                0.0
            };
            let score = weights.w_cap * cap
                + weights.w_cost * cost
                + weights.w_lat * lat
                + weights.w_ctx * ctx
                + adj
                - dep;
            ScoredModel {
                model: m.key(),
                provider: m.provider.clone(),
                model_id: m.model_id.clone(),
                pricing_tier: pricing_tier_value(m.pricing_tier).to_string(),
                terms: Terms {
                    cap: round_half_even(cap, 2),
                    cost: round_half_even(cost, 2),
                    lat: round_half_even(lat, 2),
                    ctx: round_half_even(ctx, 2),
                    adj: round_half_even(adj, 2),
                    dep: round_half_even(dep, 2),
                },
                score: round_half_even(score, 3),
            }
        })
        .collect();
    rows.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
    rows
}

fn pricing_tier_value(t: PricingTier) -> &'static str {
    match t {
        PricingTier::Free => "free",
        PricingTier::Low => "low",
        PricingTier::Medium => "medium",
        PricingTier::High => "high",
        PricingTier::Frontier => "frontier",
    }
}

/// Mirrors `engine.pick_fallback` (ROUTING_RULES.md §5).
pub fn pick_fallback(
    ranked: &[ScoredModel],
    models_by_key: &HashMap<String, &ModelEntry>,
    eligible_ids: &HashSet<String>,
) -> Option<ScoredModel> {
    let rec = ranked.first()?;
    let rec_model = *models_by_key.get(&rec.model)?;

    for fb_id in &rec_model.fallback {
        for row in &ranked[1..] {
            if &row.model_id == fb_id && eligible_ids.contains(&row.model_id) {
                return Some(row.clone());
            }
        }
    }
    for row in &ranked[1..] {
        let cand = *models_by_key.get(&row.model).unwrap();
        if cand.provider != rec_model.provider
            || pricing_tier_rank(cand.pricing_tier) < pricing_tier_rank(rec_model.pricing_tier)
        {
            return Some(row.clone());
        }
    }
    ranked.get(1).cloned()
}

#[derive(Debug, Clone, Serialize)]
pub struct RouteResult {
    pub weights: HashMap<&'static str, f64>,
    pub weight_shifts: Vec<String>,
    pub excluded: Vec<Excluded>,
    pub scores: Vec<ScoredModel>,
    pub recommendation: Option<ScoredModel>,
    pub fallback: Option<ScoredModel>,
    pub manual_suggestion: Option<String>,
}

/// Mirrors `engine.route`: full routing pass — filter -> weight -> score ->
/// recommend + fallback.
pub fn route(
    models: &[ModelEntry],
    cls: &Classification,
    base_weights: Weights,
    prefer: Option<&str>,
) -> RouteResult {
    let (weights, shifts) = weights_for(cls, base_weights, prefer);
    let (eligible, excluded) = eligibility(models, cls);
    let models_by_key: HashMap<String, &ModelEntry> = models.iter().map(|m| (m.key(), m)).collect();

    if eligible.is_empty() {
        let manual = models.iter().find(|m| m.provider == "manual");
        return RouteResult {
            weights: weights.as_map(),
            weight_shifts: shifts,
            excluded,
            scores: vec![],
            recommendation: None,
            fallback: None,
            manual_suggestion: manual.map(|m| m.key()),
        };
    }

    let ranked = score_models(&eligible, cls, weights);
    let eligible_ids: HashSet<String> = eligible.iter().map(|m| m.model_id.clone()).collect();
    let fallback = pick_fallback(&ranked, &models_by_key, &eligible_ids);
    RouteResult {
        weights: weights.as_map(),
        weight_shifts: shifts,
        excluded,
        recommendation: ranked.first().cloned(),
        scores: ranked,
        fallback,
        manual_suggestion: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use agentrouter_core::{ApprovalLevel, OutputType};

    fn model(id: &str, ctx: u32, tier: &str, coding: u8) -> ModelEntry {
        let yaml = format!(
            "provider: p\nmodel_id: {id}\ncontext_window: {ctx}\nmax_output_tokens: 8000\npricing_tier: {tier}\nlatency_tier: medium\nability: {{coding: {coding}, reasoning: {coding}, writing: {coding}}}\ntool_support: []\nvision_support: false\ndeprecation_status: active\n",
        );
        serde_yaml::from_str(&yaml).unwrap()
    }

    fn cls(context_tokens: u32, task_type: TaskType, complexity: Level) -> Classification {
        Classification {
            task_type,
            complexity,
            risk: Level::Low,
            context_tokens,
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
    fn context_filter_excludes_undersized_model() {
        let big = model("big", 400_000, "medium", 8);
        let small = model("small", 100_000, "low", 9);
        let models = vec![big, small];
        let c = cls(300_000, TaskType::Coding, Level::High);
        let result = route(&models, &c, Weights::default(), None);
        assert_eq!(result.recommendation.unwrap().model_id, "big");
        assert!(result.excluded.iter().any(|e| e.model.contains("small")));
    }

    #[test]
    fn stronger_coder_wins_on_high_complexity() {
        let strong = model("strong", 100_000, "frontier", 10);
        let weak = model("weak", 100_000, "frontier", 5);
        let models = vec![strong, weak];
        let c = cls(4000, TaskType::Coding, Level::High);
        let result = route(&models, &c, Weights::default(), None);
        assert_eq!(result.recommendation.unwrap().model_id, "strong");
    }
}
