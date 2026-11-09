//! Pure routing weight policy, ported from `agentrouter.engine.weights_for`.
//! Python remains authoritative. This crate is an isolated parity proof,
//! not an execution or provider adapter.

use agentrouter_core::{Classification, ContextBand, Level};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Weights {
    pub w_cap: f64,
    pub w_cost: f64,
    pub w_lat: f64,
    pub w_ctx: f64,
}

impl Default for Weights {
    fn default() -> Self {
        Self {
            w_cap: 0.45,
            w_cost: 0.25,
            w_lat: 0.15,
            w_ctx: 0.15,
        }
    }
}

#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Preference {
    Quality,
    Cheap,
    Fast,
    Balanced,
}

impl Preference {
    fn weights(self) -> Weights {
        match self {
            Self::Quality => Weights {
                w_cap: 0.65,
                w_cost: 0.10,
                w_lat: 0.10,
                w_ctx: 0.15,
            },
            Self::Cheap => Weights {
                w_cap: 0.20,
                w_cost: 0.55,
                w_lat: 0.10,
                w_ctx: 0.15,
            },
            Self::Fast => Weights {
                w_cap: 0.25,
                w_cost: 0.15,
                w_lat: 0.45,
                w_ctx: 0.15,
            },
            Self::Balanced => Weights::default(),
        }
    }

    fn label(self) -> &'static str {
        match self {
            Self::Quality => "quality",
            Self::Cheap => "cheap",
            Self::Fast => "fast",
            Self::Balanced => "balanced",
        }
    }
}

/// Preserve Python's ordered shift trail and preference precedence.
pub fn weights_for(
    classification: &Classification,
    base: Option<Weights>,
    preference: Option<Preference>,
) -> (Weights, Vec<String>) {
    if let Some(preference) = preference {
        return (
            preference.weights(),
            vec![format!(
                "preference={} -> fixed weights",
                preference.label()
            )],
        );
    }

    let mut weights = base.unwrap_or_default();
    let mut shifts = Vec::new();
    if classification.complexity == Level::High || classification.risk == Level::High {
        weights.w_cap = 0.55;
        weights.w_cost = 0.15;
        shifts.push("complexity/risk=high -> w_cap 0.55, w_cost 0.15".to_owned());
    } else if classification.complexity == Level::Low {
        weights.w_cap = 0.35;
        weights.w_cost = 0.35;
        shifts.push("complexity=low -> w_cap 0.35, w_cost 0.35".to_owned());
    }
    if classification.context_band == ContextBand::Large {
        weights.w_ctx = 0.25;
        weights.w_lat = 0.05;
        shifts.push("context=large -> w_ctx 0.25, w_lat 0.05".to_owned());
    }
    (weights, shifts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use agentrouter_core::{ApprovalLevel, OutputType, TaskType};

    fn classification(complexity: Level, risk: Level, context_band: ContextBand) -> Classification {
        Classification {
            task_type: TaskType::Coding,
            complexity,
            risk,
            context_tokens: 100,
            context_band,
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
    fn risk_and_context_shift_independently() {
        let cls = classification(Level::Low, Level::High, ContextBand::Large);
        let (weights, shifts) = weights_for(&cls, None, None);
        assert_eq!(
            weights,
            Weights {
                w_cap: 0.55,
                w_cost: 0.15,
                w_lat: 0.05,
                w_ctx: 0.25
            }
        );
        assert_eq!(shifts.len(), 2);
    }

    #[test]
    fn explicit_preference_wins_over_shifts_and_custom_base() {
        let cls = classification(Level::High, Level::High, ContextBand::Large);
        let custom = Weights {
            w_cap: 0.1,
            w_cost: 0.2,
            w_lat: 0.3,
            w_ctx: 0.4,
        };
        let (weights, shifts) = weights_for(&cls, Some(custom), Some(Preference::Cheap));
        assert_eq!(weights, Preference::Cheap.weights());
        assert_eq!(shifts, ["preference=cheap -> fixed weights"]);
    }

    #[test]
    fn unknown_preference_fails_closed() {
        assert!(serde_json::from_str::<Preference>("\"unknown\"").is_err());
    }
}
