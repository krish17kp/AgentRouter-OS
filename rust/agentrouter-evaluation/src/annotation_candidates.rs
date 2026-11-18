//! Deterministic, unlabelled annotation candidate generation mirrored from
//! `agentrouter.annotation.candidates`.

use serde::{Deserialize, Serialize};

use crate::annotation_packs::shuffle_python_seed;
use crate::annotation_schema::Candidate;

const BANK_JSON: &str = include_str!("../assets/annotation_candidates.json");

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct CandidateTemplate {
    pub category: String,
    pub scope: String,
    pub prompt: String,
}

pub fn candidate_bank() -> Result<Vec<CandidateTemplate>, String> {
    serde_json::from_str(BANK_JSON).map_err(|error| error.to_string())
}

/// Build deterministic candidate records without inferring annotation labels.
/// `count` follows Python slicing, including negative values.
pub fn generate(count: Option<i64>, seed: &str) -> Result<Vec<Candidate>, String> {
    let mut templates = candidate_bank()?;
    shuffle_python_seed(&mut templates, seed)?;
    let take = match count {
        None => templates.len(),
        Some(count) if count >= 0 => (count as usize).min(templates.len()),
        Some(count) => templates
            .len()
            .saturating_sub(count.unsigned_abs().min(templates.len() as u64) as usize),
    };
    templates.truncate(take);
    templates
        .into_iter()
        .enumerate()
        .map(|(index, template)| {
            let candidate = Candidate {
                id: format!("cand-{:04}", index + 1),
                prompt: template.prompt,
                category: template.category.clone(),
                source: "generated_candidate".to_owned(),
                template: Some(format!("{}/{}", template.category, template.scope)),
                notes: None,
            };
            candidate.validate()?;
            Ok(candidate)
        })
        .collect()
}
