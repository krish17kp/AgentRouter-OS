//! Public evaluation package facade, matching `agentrouter.evaluation`.

pub use crate::{EvaluationCase, ExpectedClassification, Provenance};

pub const PUBLIC_EXPORTS: [&str; 3] = ["EvaluationCase", "ExpectedClassification", "Provenance"];
