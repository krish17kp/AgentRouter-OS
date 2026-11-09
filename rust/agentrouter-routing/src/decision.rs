//! Full static routing decision, matching `agentrouter.engine` for validated
//! registry projections. Host execution and live availability are separate.

use crate::{weights_for, Preference, Weights};
use agentrouter_core::{
    Classification, DeprecationStatus, LatencyTier, Level, PricingTier, TaskType,
};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Deserialize)]
pub struct Ability {
    pub coding: u8,
    pub reasoning: u8,
    pub writing: u8,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RouteModel {
    pub provider: String,
    pub model_id: String,
    pub context_window: u64,
    pub pricing_tier: PricingTier,
    pub latency_tier: LatencyTier,
    pub ability: Ability,
    pub tool_support: Vec<String>,
    pub vision_support: bool,
    pub ideal_use_cases: Vec<String>,
    pub avoid_use_cases: Vec<String>,
    pub deprecation_status: DeprecationStatus,
    pub fallback: Vec<String>,
}

impl RouteModel {
    fn key(&self) -> String {
        format!("{}/{}", self.provider, self.model_id)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Exclusion {
    pub model: String,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Terms {
    pub cap: f64,
    pub cost: f64,
    pub lat: f64,
    pub ctx: f64,
    pub adj: f64,
    pub dep: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ScoreRow {
    pub model: String,
    pub provider: String,
    pub model_id: String,
    pub pricing_tier: PricingTier,
    pub terms: Terms,
    pub score: f64,
}

#[derive(Debug, Serialize)]
pub struct Decision {
    pub weights: Weights,
    pub weight_shifts: Vec<String>,
    pub excluded: Vec<Exclusion>,
    pub scores: Vec<ScoreRow>,
    pub recommendation: Option<ScoreRow>,
    pub fallback: Option<ScoreRow>,
    pub manual_suggestion: Option<String>,
}

fn tool_satisfied(required: &str, supported: &HashSet<&str>) -> bool {
    supported.contains(required)
        || (required == "web" && supported.contains("web-search"))
        || (required == "web-search" && supported.contains("web"))
        || (required == "tool-use" && supported.contains("function-calling"))
        || (required == "function-calling" && supported.contains("tool-use"))
}

pub fn eligibility<'a>(
    models: &'a [RouteModel],
    cls: &Classification,
) -> (Vec<&'a RouteModel>, Vec<Exclusion>) {
    let mut eligible = Vec::new();
    let mut excluded = Vec::new();
    for model in models {
        let reason = if model.deprecation_status == DeprecationStatus::Retired {
            Some("retired".to_owned())
        } else if model.context_window < u64::from(cls.context_tokens) {
            Some(format!(
                "context {} < {}",
                model.context_window, cls.context_tokens
            ))
        } else {
            let support: HashSet<&str> = model.tool_support.iter().map(String::as_str).collect();
            let missing: Vec<&str> = cls
                .tool_needs
                .iter()
                .map(String::as_str)
                .filter(|tool| *tool != "vision" && !tool_satisfied(tool, &support))
                .collect();
            if !missing.is_empty() {
                Some(format!("missing tools: {}", missing.join(",")))
            } else if cls.tool_needs.iter().any(|tool| tool == "vision") && !model.vision_support {
                Some("no vision support".to_owned())
            } else {
                None
            }
        };
        if let Some(reason) = reason {
            excluded.push(Exclusion {
                model: model.key(),
                reason,
            });
        } else {
            eligible.push(model);
        }
    }
    (eligible, excluded)
}

fn capability(model: &RouteModel, task_type: TaskType) -> f64 {
    let a = &model.ability;
    match task_type {
        TaskType::Coding => 0.0 + f64::from(a.coding) / 10.0,
        TaskType::Reasoning => 0.0 + f64::from(a.reasoning) / 10.0,
        TaskType::Writing => 0.0 + f64::from(a.writing) / 10.0,
        TaskType::Analysis => {
            0.0 + f64::from(a.reasoning) / 10.0 * 0.7 + f64::from(a.writing) / 10.0 * 0.3
        }
        TaskType::Summarization => {
            0.0 + f64::from(a.writing) / 10.0 * 0.7 + f64::from(a.reasoning) / 10.0 * 0.3
        }
        TaskType::General => {
            0.0 + f64::from(a.coding) / 10.0 * (1.0 / 3.0)
                + f64::from(a.reasoning) / 10.0 * (1.0 / 3.0)
                + f64::from(a.writing) / 10.0 * (1.0 / 3.0)
        }
    }
}

fn cost_fit(level: Level, tier: PricingTier) -> f64 {
    match level {
        Level::Low => match tier {
            PricingTier::Free => 1.0,
            PricingTier::Low => 0.9,
            PricingTier::Medium => 0.6,
            PricingTier::High => 0.3,
            PricingTier::Frontier => 0.1,
        },
        Level::Medium => match tier {
            PricingTier::Free => 0.7,
            PricingTier::Low => 0.8,
            PricingTier::Medium => 1.0,
            PricingTier::High => 0.8,
            PricingTier::Frontier => 0.6,
        },
        Level::High => match tier {
            PricingTier::Free => 0.4,
            PricingTier::Low => 0.5,
            PricingTier::Medium => 0.7,
            PricingTier::High => 0.9,
            PricingTier::Frontier => 1.0,
        },
    }
}

fn latency_fit(level: Level, tier: LatencyTier) -> f64 {
    match level {
        Level::Low => match tier {
            LatencyTier::Fast => 1.0,
            LatencyTier::Medium => 0.7,
            LatencyTier::Slow => 0.3,
        },
        Level::Medium => match tier {
            LatencyTier::Fast => 0.9,
            LatencyTier::Medium => 0.8,
            LatencyTier::Slow => 0.5,
        },
        Level::High => match tier {
            LatencyTier::Fast => 0.8,
            LatencyTier::Medium => 0.8,
            LatencyTier::Slow => 0.6,
        },
    }
}

fn context_fit(model: &RouteModel, cls: &Classification) -> f64 {
    let ratio = model.context_window as f64 / f64::from(cls.context_tokens.max(1));
    if ratio < 2.0 {
        0.7
    } else if ratio < 16.0 {
        1.0
    } else {
        0.6
    }
}

fn task_label(task_type: TaskType) -> &'static str {
    match task_type {
        TaskType::Coding => "coding",
        TaskType::Reasoning => "reasoning",
        TaskType::Writing => "writing",
        TaskType::Analysis => "analysis",
        TaskType::Summarization => "summarization",
        TaskType::General => "general",
    }
}

fn python_round(value: f64, digits: u32) -> f64 {
    if value == 0.0 {
        return value;
    }
    let bits = value.abs().to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32;
    if exponent == 0 || exponent == 0x7ff {
        return value;
    }
    let significand = u128::from((bits & ((1_u64 << 52) - 1)) | (1_u64 << 52));
    let binary_exp = exponent - 1023 - 52;
    if binary_exp >= 0 {
        return value;
    }
    if binary_exp <= -127 {
        return 0.0_f64.copysign(value);
    }
    let scale = 10_u128.pow(digits);
    let numerator = significand * scale;
    let denominator = 1_u128 << (-binary_exp as u32);
    let quotient = numerator / denominator;
    let remainder = numerator % denominator;
    let rounded =
        if remainder > denominator / 2 || (remainder == denominator / 2 && quotient % 2 == 1) {
            quotient + 1
        } else {
            quotient
        };
    (rounded as f64 / scale as f64).copysign(value)
}

fn score(model: &RouteModel, cls: &Classification, w: Weights) -> ScoreRow {
    let cap = capability(model, cls.task_type);
    let cost = cost_fit(cls.complexity, model.pricing_tier);
    let lat = latency_fit(cls.complexity, model.latency_tier);
    let ctx = context_fit(model, cls);
    let label = task_label(cls.task_type);
    let mut adj = 0.0;
    if model.ideal_use_cases.iter().any(|item| item == label) {
        adj += 0.05;
    }
    if model.avoid_use_cases.iter().any(|item| item == label) {
        adj -= 0.10;
    }
    let dep = if model.deprecation_status == DeprecationStatus::Deprecated {
        0.2
    } else {
        0.0
    };
    let total = w.w_cap * cap + w.w_cost * cost + w.w_lat * lat + w.w_ctx * ctx + adj - dep;
    ScoreRow {
        model: model.key(),
        provider: model.provider.clone(),
        model_id: model.model_id.clone(),
        pricing_tier: model.pricing_tier,
        terms: Terms {
            cap: python_round(cap, 2),
            cost: python_round(cost, 2),
            lat: python_round(lat, 2),
            ctx: python_round(ctx, 2),
            adj: python_round(adj, 2),
            dep: python_round(dep, 2),
        },
        score: python_round(total, 3),
    }
}

fn tier_rank(tier: PricingTier) -> u8 {
    match tier {
        PricingTier::Free => 0,
        PricingTier::Low => 1,
        PricingTier::Medium => 2,
        PricingTier::High => 3,
        PricingTier::Frontier => 4,
    }
}

fn fallback(
    ranked: &[ScoreRow],
    by_key: &HashMap<String, &RouteModel>,
    eligible_ids: &HashSet<&str>,
) -> Option<ScoreRow> {
    let first = ranked.first()?;
    let rec = by_key.get(&first.model)?;
    for fb_id in &rec.fallback {
        if let Some(row) = ranked
            .iter()
            .skip(1)
            .find(|row| row.model_id == *fb_id && eligible_ids.contains(row.model_id.as_str()))
        {
            return Some(row.clone());
        }
    }
    for row in ranked.iter().skip(1) {
        let cand = by_key.get(&row.model)?;
        if cand.provider != rec.provider
            || tier_rank(cand.pricing_tier) < tier_rank(rec.pricing_tier)
        {
            return Some(row.clone());
        }
    }
    ranked.get(1).cloned()
}

pub fn route(
    models: &[RouteModel],
    cls: &Classification,
    base: Option<Weights>,
    preference: Option<Preference>,
) -> Decision {
    let (weights, weight_shifts) = weights_for(cls, base, preference);
    let (eligible, excluded) = eligibility(models, cls);
    let by_key: HashMap<String, &RouteModel> =
        models.iter().map(|model| (model.key(), model)).collect();
    if eligible.is_empty() {
        return Decision {
            weights,
            weight_shifts,
            excluded,
            scores: vec![],
            recommendation: None,
            fallback: None,
            manual_suggestion: models
                .iter()
                .find(|model| model.provider == "manual")
                .map(RouteModel::key),
        };
    }
    let eligible_ids: HashSet<&str> = eligible
        .iter()
        .map(|model| model.model_id.as_str())
        .collect();
    let mut scores: Vec<ScoreRow> = eligible
        .iter()
        .map(|model| score(model, cls, weights))
        .collect();
    scores.sort_by(|left, right| right.score.total_cmp(&left.score));
    let recommendation = scores.first().cloned();
    let fallback = fallback(&scores, &by_key, &eligible_ids);
    Decision {
        weights,
        weight_shifts,
        excluded,
        scores,
        recommendation,
        fallback,
        manual_suggestion: None,
    }
}
