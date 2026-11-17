//! Safe workflow planning for future multi-agent orchestration.
//!
//! This crate plans a bounded dependency graph only. It never dispatches a
//! model, runs a command, grants tools, or mutates a workspace. The explicit
//! separation lets cycle, budget, duplicate-execution, and conflicting-write
//! guards be tested before any owner-authorized execution adapter exists.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkflowStep {
    pub id: String,
    #[serde(default)]
    pub depends_on: Vec<String>,
    #[serde(default)]
    pub side_effect_key: Option<String>,
    #[serde(default = "default_attempts")]
    pub max_attempts: u32,
    pub estimated_cost: u64,
}

fn default_attempts() -> u32 {
    1
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkflowPlan {
    pub ordered_steps: Vec<String>,
    pub parallel_groups: Vec<Vec<String>>,
    pub estimated_cost: u64,
    pub max_steps: usize,
    pub execution_enabled: bool,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum WorkflowError {
    #[error("workflow must contain at least one step")]
    Empty,
    #[error("workflow step id must not be empty")]
    EmptyId,
    #[error("duplicate workflow step '{0}'")]
    DuplicateId(String),
    #[error("step '{step}' depends on unknown step '{dependency}'")]
    UnknownDependency { step: String, dependency: String },
    #[error("workflow dependency graph contains a cycle")]
    Cycle,
    #[error("workflow has {actual} steps, exceeding the {limit}-step budget")]
    StepBudget { actual: usize, limit: usize },
    #[error("workflow estimated cost {actual} exceeds the {limit} budget")]
    CostBudget { actual: u64, limit: u64 },
    #[error("parallel steps conflict on side-effect key '{0}'")]
    ParallelConflict(String),
    #[error("step '{0}' must allow at least one attempt")]
    InvalidAttempts(String),
}

/// Validate and schedule a workflow into safe dependency levels.
pub fn plan(
    steps: &[WorkflowStep],
    max_steps: usize,
    max_cost: u64,
) -> Result<WorkflowPlan, WorkflowError> {
    if steps.is_empty() {
        return Err(WorkflowError::Empty);
    }
    if steps.len() > max_steps {
        return Err(WorkflowError::StepBudget {
            actual: steps.len(),
            limit: max_steps,
        });
    }
    let mut by_id = BTreeMap::new();
    for step in steps {
        if step.id.is_empty() {
            return Err(WorkflowError::EmptyId);
        }
        if step.max_attempts == 0 {
            return Err(WorkflowError::InvalidAttempts(step.id.clone()));
        }
        if by_id.insert(step.id.clone(), step).is_some() {
            return Err(WorkflowError::DuplicateId(step.id.clone()));
        }
    }
    let estimated_cost = steps.iter().try_fold(0_u64, |total, step| {
        total
            .checked_add(step.estimated_cost)
            .ok_or(WorkflowError::CostBudget {
                actual: u64::MAX,
                limit: max_cost,
            })
    })?;
    if estimated_cost > max_cost {
        return Err(WorkflowError::CostBudget {
            actual: estimated_cost,
            limit: max_cost,
        });
    }

    let mut indegree = BTreeMap::<String, usize>::new();
    let mut edges = BTreeMap::<String, Vec<String>>::new();
    for step in steps {
        indegree.insert(step.id.clone(), step.depends_on.len());
        for dependency in &step.depends_on {
            if !by_id.contains_key(dependency) {
                return Err(WorkflowError::UnknownDependency {
                    step: step.id.clone(),
                    dependency: dependency.clone(),
                });
            }
            edges
                .entry(dependency.clone())
                .or_default()
                .push(step.id.clone());
        }
    }

    let mut ready = indegree
        .iter()
        .filter_map(|(id, count)| (*count == 0).then_some(id.clone()))
        .collect::<BTreeSet<_>>();
    let mut ordered_steps = Vec::with_capacity(steps.len());
    let mut parallel_groups = Vec::new();
    while !ready.is_empty() {
        let group = ready.iter().cloned().collect::<Vec<_>>();
        let mut side_effects = BTreeSet::new();
        for id in &group {
            if let Some(key) = &by_id[id].side_effect_key {
                if !side_effects.insert(key.clone()) {
                    return Err(WorkflowError::ParallelConflict(key.clone()));
                }
            }
        }
        parallel_groups.push(group.clone());
        ordered_steps.extend(group.iter().cloned());
        let mut next = BTreeSet::new();
        for id in group {
            if let Some(children) = edges.get(&id) {
                for child in children {
                    let count = indegree
                        .get_mut(child)
                        .expect("dependency child exists in indegree");
                    *count -= 1;
                    if *count == 0 {
                        next.insert(child.clone());
                    }
                }
            }
        }
        ready = next;
    }
    if ordered_steps.len() != steps.len() {
        return Err(WorkflowError::Cycle);
    }
    Ok(WorkflowPlan {
        ordered_steps,
        parallel_groups,
        estimated_cost,
        max_steps,
        execution_enabled: false,
    })
}

/// Convenience constructor for a single-step workflow.
pub fn single_step(id: impl Into<String>, estimated_cost: u64) -> WorkflowStep {
    WorkflowStep {
        id: id.into(),
        depends_on: Vec::new(),
        side_effect_key: None,
        max_attempts: 1,
        estimated_cost,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plans_deterministic_dependency_levels_without_execution() {
        let steps = vec![
            single_step("a", 2),
            WorkflowStep {
                id: "b".into(),
                depends_on: vec!["a".into()],
                side_effect_key: Some("file:b".into()),
                max_attempts: 2,
                estimated_cost: 3,
            },
            WorkflowStep {
                id: "c".into(),
                depends_on: vec!["a".into()],
                side_effect_key: Some("file:c".into()),
                max_attempts: 1,
                estimated_cost: 4,
            },
        ];
        let plan = plan(&steps, 3, 9).expect("valid DAG");
        assert_eq!(plan.ordered_steps, ["a", "b", "c"]);
        assert_eq!(
            plan.parallel_groups,
            vec![
                vec!["a".to_string()],
                vec!["b".to_string(), "c".to_string()]
            ]
        );
        assert_eq!(plan.estimated_cost, 9);
        assert!(!plan.execution_enabled);
    }

    #[test]
    fn rejects_cycles_and_parallel_side_effect_conflicts() {
        let cycle = vec![
            WorkflowStep {
                id: "a".into(),
                depends_on: vec!["b".into()],
                ..single_step("unused", 1)
            },
            WorkflowStep {
                id: "b".into(),
                depends_on: vec!["a".into()],
                ..single_step("unused", 1)
            },
        ];
        assert_eq!(plan(&cycle, 2, 2), Err(WorkflowError::Cycle));

        let conflict = vec![
            WorkflowStep {
                id: "a".into(),
                side_effect_key: Some("same".into()),
                ..single_step("unused", 1)
            },
            WorkflowStep {
                id: "b".into(),
                side_effect_key: Some("same".into()),
                ..single_step("unused", 1)
            },
        ];
        assert_eq!(
            plan(&conflict, 2, 2),
            Err(WorkflowError::ParallelConflict("same".into()))
        );
    }

    #[test]
    fn enforces_step_and_cost_budgets_before_planning() {
        let steps = vec![single_step("a", 4), single_step("b", 4)];
        assert!(matches!(
            plan(&steps, 1, 8),
            Err(WorkflowError::StepBudget { .. })
        ));
        assert!(matches!(
            plan(&steps, 2, 7),
            Err(WorkflowError::CostBudget { .. })
        ));
    }
}
