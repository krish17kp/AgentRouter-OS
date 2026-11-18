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
    #[serde(default)]
    pub idempotency_key: Option<String>,
    #[serde(default)]
    pub required_tools: Vec<String>,
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StepState {
    Pending,
    Running,
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkflowRunState {
    Pending,
    Running,
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkflowResult {
    pub state: WorkflowRunState,
    pub steps: BTreeMap<String, StepState>,
    pub attempts: BTreeMap<String, u32>,
    pub outputs: BTreeMap<String, String>,
    pub errors: BTreeMap<String, String>,
    pub execution_enabled: bool,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    #[error("unknown workflow step '{0}'")]
    UnknownStep(String),
    #[error("workflow step '{0}' is not ready")]
    NotReady(String),
    #[error("workflow step '{0}' is not running")]
    NotRunning(String),
    #[error("workflow step '{0}' is already terminal")]
    Terminal(String),
    #[error("workflow has been cancelled")]
    Cancelled,
}

/// A bounded workflow lifecycle state machine. It records readiness, retries,
/// cancellation, and result aggregation but deliberately does not dispatch an
/// agent, call a tool/provider, or mutate a workspace.
#[derive(Debug, Clone)]
pub struct WorkflowRuntime {
    steps: BTreeMap<String, WorkflowStep>,
    states: BTreeMap<String, StepState>,
    attempts: BTreeMap<String, u32>,
    outputs: BTreeMap<String, String>,
    errors: BTreeMap<String, String>,
    cancelled: bool,
}

impl WorkflowRuntime {
    pub fn new(steps: &[WorkflowStep], policy: WorkflowPolicy) -> Result<Self, WorkflowError> {
        plan_with_policy(steps, policy)?;
        let steps = steps
            .iter()
            .map(|step| (step.id.clone(), step.clone()))
            .collect::<BTreeMap<_, _>>();
        let states = steps
            .keys()
            .map(|id| (id.clone(), StepState::Pending))
            .collect();
        let attempts = steps.keys().map(|id| (id.clone(), 0)).collect();
        Ok(Self {
            steps,
            states,
            attempts,
            outputs: BTreeMap::new(),
            errors: BTreeMap::new(),
            cancelled: false,
        })
    }

    pub fn ready_steps(&self) -> Vec<String> {
        if self.cancelled {
            return Vec::new();
        }
        self.steps
            .values()
            .filter(|step| self.states[&step.id] == StepState::Pending)
            .filter(|step| {
                step.depends_on
                    .iter()
                    .all(|dependency| self.states[dependency] == StepState::Succeeded)
            })
            .map(|step| step.id.clone())
            .collect()
    }

    pub fn start(&mut self, id: &str) -> Result<(), RuntimeError> {
        if self.cancelled {
            return Err(RuntimeError::Cancelled);
        }
        let state = self
            .states
            .get(id)
            .ok_or_else(|| RuntimeError::UnknownStep(id.to_owned()))?;
        if *state != StepState::Pending || !self.ready_steps().iter().any(|ready| ready == id) {
            return Err(RuntimeError::NotReady(id.to_owned()));
        }
        self.states.insert(id.to_owned(), StepState::Running);
        let attempts = self.attempts.entry(id.to_owned()).or_default();
        *attempts = attempts.saturating_add(1);
        Ok(())
    }

    pub fn succeed(&mut self, id: &str, output: impl Into<String>) -> Result<(), RuntimeError> {
        self.require_running(id)?;
        self.states.insert(id.to_owned(), StepState::Succeeded);
        self.outputs.insert(id.to_owned(), output.into());
        self.errors.remove(id);
        Ok(())
    }

    pub fn fail(&mut self, id: &str, error: impl Into<String>) -> Result<bool, RuntimeError> {
        self.require_running(id)?;
        let step = self
            .steps
            .get(id)
            .ok_or_else(|| RuntimeError::UnknownStep(id.to_owned()))?;
        let message = error.into();
        self.errors.insert(id.to_owned(), message);
        if self.attempts[id] < step.max_attempts && !self.cancelled {
            self.states.insert(id.to_owned(), StepState::Pending);
            return Ok(true);
        }
        self.states.insert(id.to_owned(), StepState::Failed);
        Ok(false)
    }

    pub fn cancel(&mut self) {
        self.cancelled = true;
        for state in self.states.values_mut() {
            if matches!(*state, StepState::Pending | StepState::Running) {
                *state = StepState::Cancelled;
            }
        }
    }

    pub fn result(&self) -> WorkflowResult {
        let state = if self.cancelled {
            WorkflowRunState::Cancelled
        } else if self
            .states
            .values()
            .any(|state| *state == StepState::Failed)
        {
            WorkflowRunState::Failed
        } else if self
            .states
            .values()
            .all(|state| *state == StepState::Succeeded)
        {
            WorkflowRunState::Succeeded
        } else if self
            .states
            .values()
            .any(|state| *state == StepState::Running)
        {
            WorkflowRunState::Running
        } else {
            WorkflowRunState::Pending
        };
        WorkflowResult {
            state,
            steps: self.states.clone(),
            attempts: self.attempts.clone(),
            outputs: self.outputs.clone(),
            errors: self.errors.clone(),
            execution_enabled: false,
        }
    }

    fn require_running(&self, id: &str) -> Result<(), RuntimeError> {
        match self.states.get(id) {
            None => Err(RuntimeError::UnknownStep(id.to_owned())),
            Some(StepState::Running) => Ok(()),
            Some(StepState::Succeeded | StepState::Failed | StepState::Cancelled) => {
                Err(RuntimeError::Terminal(id.to_owned()))
            }
            Some(StepState::Pending) => Err(RuntimeError::NotRunning(id.to_owned())),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkflowPolicy {
    pub max_steps: usize,
    pub max_cost: u64,
    #[serde(default)]
    pub allowed_tools: BTreeSet<String>,
}

impl WorkflowPolicy {
    pub fn new(max_steps: usize, max_cost: u64) -> Self {
        Self {
            max_steps,
            max_cost,
            allowed_tools: BTreeSet::new(),
        }
    }
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
    #[error("step '{step}' declares dependency '{dependency}' more than once")]
    DuplicateDependency { step: String, dependency: String },
    #[error("workflow dependency graph contains a cycle")]
    Cycle,
    #[error("workflow has {actual} steps, exceeding the {limit}-step budget")]
    StepBudget { actual: usize, limit: usize },
    #[error("workflow estimated cost {actual} exceeds the {limit} budget")]
    CostBudget { actual: u64, limit: u64 },
    #[error("parallel steps conflict on side-effect key '{0}'")]
    ParallelConflict(String),
    #[error("step '{0}' has an empty side-effect key")]
    EmptySideEffectKey(String),
    #[error("step '{step}' requires tool '{tool}', which is not allowed")]
    ToolNotAllowed { step: String, tool: String },
    #[error("duplicate workflow idempotency key '{0}'")]
    DuplicateIdempotencyKey(String),
    #[error("step '{0}' must allow at least one attempt")]
    InvalidAttempts(String),
}

/// Validate and schedule a workflow into safe dependency levels.
pub fn plan(
    steps: &[WorkflowStep],
    max_steps: usize,
    max_cost: u64,
) -> Result<WorkflowPlan, WorkflowError> {
    plan_with_policy(steps, WorkflowPolicy::new(max_steps, max_cost))
}

/// Validate and schedule a workflow with an explicit tool allowlist.
pub fn plan_with_policy(
    steps: &[WorkflowStep],
    policy: WorkflowPolicy,
) -> Result<WorkflowPlan, WorkflowError> {
    if steps.is_empty() {
        return Err(WorkflowError::Empty);
    }
    if steps.len() > policy.max_steps {
        return Err(WorkflowError::StepBudget {
            actual: steps.len(),
            limit: policy.max_steps,
        });
    }
    let mut by_id = BTreeMap::new();
    let mut idempotency_keys = BTreeSet::new();
    for step in steps {
        if step.id.is_empty() {
            return Err(WorkflowError::EmptyId);
        }
        if step.max_attempts == 0 {
            return Err(WorkflowError::InvalidAttempts(step.id.clone()));
        }
        if step.side_effect_key.as_deref() == Some("") {
            return Err(WorkflowError::EmptySideEffectKey(step.id.clone()));
        }
        for tool in &step.required_tools {
            if tool.is_empty() || !policy.allowed_tools.contains(tool) {
                return Err(WorkflowError::ToolNotAllowed {
                    step: step.id.clone(),
                    tool: tool.clone(),
                });
            }
        }
        if let Some(key) = &step.idempotency_key {
            if key.is_empty() || !idempotency_keys.insert(key.clone()) {
                return Err(WorkflowError::DuplicateIdempotencyKey(key.clone()));
            }
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
                limit: policy.max_cost,
            })
    })?;
    if estimated_cost > policy.max_cost {
        return Err(WorkflowError::CostBudget {
            actual: estimated_cost,
            limit: policy.max_cost,
        });
    }

    let mut indegree = BTreeMap::<String, usize>::new();
    let mut edges = BTreeMap::<String, Vec<String>>::new();
    for step in steps {
        indegree.insert(step.id.clone(), step.depends_on.len());
        let mut dependencies = BTreeSet::new();
        for dependency in &step.depends_on {
            if !dependencies.insert(dependency) {
                return Err(WorkflowError::DuplicateDependency {
                    step: step.id.clone(),
                    dependency: dependency.clone(),
                });
            }
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
        max_steps: policy.max_steps,
        execution_enabled: false,
    })
}

/// Convenience constructor for a single-step workflow.
pub fn single_step(id: impl Into<String>, estimated_cost: u64) -> WorkflowStep {
    WorkflowStep {
        id: id.into(),
        depends_on: Vec::new(),
        side_effect_key: None,
        idempotency_key: None,
        required_tools: Vec::new(),
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
                idempotency_key: None,
                required_tools: Vec::new(),
                max_attempts: 2,
                estimated_cost: 3,
            },
            WorkflowStep {
                id: "c".into(),
                depends_on: vec!["a".into()],
                side_effect_key: Some("file:c".into()),
                idempotency_key: None,
                required_tools: Vec::new(),
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

    #[test]
    fn enforces_tool_allowlist_and_unique_idempotency_keys() {
        let tool_step = WorkflowStep {
            id: "tool".into(),
            required_tools: vec!["shell".into()],
            ..single_step("unused", 1)
        };
        let denied = plan(std::slice::from_ref(&tool_step), 1, 1).expect_err("tool must be denied");
        assert_eq!(
            denied,
            WorkflowError::ToolNotAllowed {
                step: "tool".into(),
                tool: "shell".into()
            }
        );

        let mut policy = WorkflowPolicy::new(2, 2);
        policy.allowed_tools.insert("shell".into());
        let mut first = tool_step;
        first.idempotency_key = Some("same-request".into());
        let mut second = single_step("second", 1);
        second.idempotency_key = Some("same-request".into());
        assert_eq!(
            plan_with_policy(&[first, second], policy),
            Err(WorkflowError::DuplicateIdempotencyKey(
                "same-request".into()
            ))
        );
    }

    #[test]
    fn rejects_duplicate_dependencies_and_empty_side_effect_keys() {
        let duplicate = WorkflowStep {
            id: "child".into(),
            depends_on: vec!["root".into(), "root".into()],
            ..single_step("unused", 1)
        };
        let root = single_step("root", 1);
        assert_eq!(
            plan(&[root, duplicate], 2, 2),
            Err(WorkflowError::DuplicateDependency {
                step: "child".into(),
                dependency: "root".into()
            })
        );

        let empty_key = WorkflowStep {
            id: "write".into(),
            side_effect_key: Some(String::new()),
            ..single_step("unused", 1)
        };
        assert_eq!(
            plan(&[empty_key], 1, 1),
            Err(WorkflowError::EmptySideEffectKey("write".into()))
        );
    }

    #[test]
    fn runtime_unlocks_dependents_and_aggregates_results_without_execution() {
        let steps = vec![
            single_step("prepare", 1),
            WorkflowStep {
                id: "write".into(),
                depends_on: vec!["prepare".into()],
                max_attempts: 1,
                ..single_step("unused", 2)
            },
        ];
        let mut runtime = WorkflowRuntime::new(&steps, WorkflowPolicy::new(2, 3)).unwrap();
        assert_eq!(runtime.ready_steps(), vec!["prepare"]);
        runtime.start("prepare").unwrap();
        runtime.succeed("prepare", "prepared").unwrap();
        assert_eq!(runtime.ready_steps(), vec!["write"]);
        runtime.start("write").unwrap();
        runtime.succeed("write", "written").unwrap();
        let result = runtime.result();
        assert_eq!(result.state, WorkflowRunState::Succeeded);
        assert_eq!(result.outputs["write"], "written");
        assert!(!result.execution_enabled);
    }

    #[test]
    fn runtime_retries_then_fails_and_cancels_pending_work() {
        let steps = vec![
            WorkflowStep {
                id: "flaky".into(),
                max_attempts: 2,
                ..single_step("unused", 1)
            },
            single_step("later", 1),
        ];
        let mut runtime = WorkflowRuntime::new(&steps, WorkflowPolicy::new(2, 2)).unwrap();
        runtime.start("flaky").unwrap();
        assert!(runtime.fail("flaky", "first").unwrap());
        assert_eq!(runtime.ready_steps(), vec!["flaky", "later"]);
        runtime.start("flaky").unwrap();
        assert!(!runtime.fail("flaky", "second").unwrap());
        assert_eq!(runtime.result().state, WorkflowRunState::Failed);

        runtime.cancel();
        assert_eq!(runtime.result().state, WorkflowRunState::Cancelled);
        assert!(runtime.start("later").is_err());
    }
}
