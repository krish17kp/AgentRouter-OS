//! Rust port of `agentrouter/classifier.py` — rule-based `classify()` over
//! the same 7 dimensions (ROUTING_RULES.md §1). Word-boundary vocabularies,
//! precedence order, and scoring are copied field-for-field from the Python
//! module so the two stay behaviorally identical; see
//! `tests/test_classifier_rust_compat.py` for the byte-for-byte check.
//!
//! The learned context-band model (`context_model.py`) is intentionally not
//! ported: Python's `_USE_LEARNED_BAND` is `False`, so that code path is
//! dead in the current shipping classifier. If it is ever flipped on, this
//! crate must be revisited together with it.

use std::sync::OnceLock;

use agentrouter_core::{ApprovalLevel, Classification, ContextBand, Level, OutputType, TaskType};
use regex::Regex;

fn matcher(words: &[&str]) -> Regex {
    let pattern = format!(
        r"(?i)\b({})\b",
        words
            .iter()
            .map(|w| regex::escape(w))
            .collect::<Vec<_>>()
            .join("|")
    );
    Regex::new(&pattern).expect("static vocabulary regex must compile")
}

macro_rules! lazy_matcher {
    ($name:ident, [$($word:expr),+ $(,)?]) => {
        fn $name() -> &'static Regex {
            static CELL: OnceLock<Regex> = OnceLock::new();
            CELL.get_or_init(|| matcher(&[$($word),+]))
        }
    };
}

lazy_matcher!(
    m_summarize,
    [
        "summarize",
        "summarise",
        "summary",
        "summriz",
        "tl;dr",
        "tldr",
        "condense",
        "recap",
        "abstract of",
    ]
);
lazy_matcher!(
    m_doc_artifacts,
    [
        "readme",
        "prd",
        "brd",
        "roadmap",
        "changelog",
        "documentation",
        "docs",
        "design doc",
        "architecture doc",
        "wiki",
        "tutorial",
        "user guide",
    ]
);
lazy_matcher!(
    m_doc_verbs,
    ["polish", "rewrite", "proofread", "proof-read"]
);
lazy_matcher!(
    m_writing,
    [
        "write a blog",
        "write an article",
        "blog post",
        "article",
        "draft",
        "email",
        "essay",
        "cover letter",
        "tweet",
        "newsletter",
        "marketing copy",
        "landing page headline",
        "short story",
        "release notes",
        "proposal",
        "paragraph",
        "press release",
        "announcement",
        "guide",
        "sales guide",
    ]
);
lazy_matcher!(
    m_build_verbs,
    [
        "build",
        "create",
        "develop",
        "implement",
        "scaffold",
        "set up",
        "stand up",
        "spin up",
        "make a",
        "make an",
    ]
);

const PROJECT_NOUNS: &[&str] = &[
    "app",
    "apps",
    "application",
    "service",
    "microservice",
    "system",
    "website",
    "web app",
    "platform",
    "cli",
    "cli tool",
    "pipeline",
    "bot",
    "extension",
    "backend",
    "frontend",
    "mvp",
    "prototype",
    "dashboard",
    "server",
];
const COMPONENT_NOUNS: &[&str] = &[
    "handler",
    "endpoint",
    "endpoints",
    "middleware",
    "component",
    "module",
    "controller",
    "model",
    "schema",
    "route",
    "form",
    "worker",
    "package",
    "api",
    "database",
    "table",
    "page",
    "toggle",
    "widget",
    "feature",
    "webhook",
    "parser",
    "job",
    "layer",
    "script",
    "code",
];

fn m_project_nouns() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| matcher(PROJECT_NOUNS))
}

fn m_component_nouns() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| {
        let combined: Vec<&str> = PROJECT_NOUNS
            .iter()
            .chain(COMPONENT_NOUNS)
            .copied()
            .collect();
        matcher(&combined)
    })
}

lazy_matcher!(
    m_software_domain,
    [
        "rag",
        "retrieval",
        "embedding",
        "embeddings",
        "vector database",
        "vector store",
        "vector db",
        "vector search",
        "chunking",
        "ingestion",
        "etl",
        "fine-tune",
        "fine tune",
        "inference pipeline",
    ]
);
lazy_matcher!(
    m_action_verbs,
    [
        "write",
        "create",
        "build",
        "develop",
        "implement",
        "add",
        "refactor",
        "fix",
        "modify",
        "update",
        "rename",
        "convert",
        "optimize",
        "optimise",
        "integrate",
        "configure",
        "scaffold",
        "patch",
        "wire",
        "store",
        "encrypt",
        "hash",
        "parse",
        "debug",
        "deploy",
        "provision",
        "install",
        "generate",
        "connect",
        "set up",
        "back up",
        "handle",
        "train",
    ]
);
lazy_matcher!(
    m_coding,
    [
        "refactor",
        "debug",
        "implement",
        "fix",
        "bug",
        "code",
        "script",
        "function",
        "endpoint",
        "unit test",
        "compile",
        "regex",
        "sql",
        "api",
        "class",
        "module",
        "one-liner",
        "bash",
        "python",
        "typescript",
        "command",
        "cli",
        "configure",
        "oauth",
        "oauth2",
        "integrate",
        "provision",
        "middleware",
        "webhook",
        "test",
        "tests",
        "hashing",
        "salting",
        "encrypt",
        "decrypt",
        "cache",
        "caching",
        "parser",
        "query",
        "database",
        "pipeline",
        "deploy",
        "deployment",
        "train",
        "rollback",
        "classifier",
        "docstring",
        "docstrings",
    ]
);
lazy_matcher!(
    m_analysis,
    [
        "analyze",
        "analyse",
        "analysis",
        "compare",
        "review",
        "evaluate",
        "assess",
        "what's wrong",
        "whats wrong",
        "audit",
        "investigate",
        "root cause",
        "look into",
    ]
);
lazy_matcher!(
    m_reasoning,
    [
        "plan",
        "design",
        "architect",
        "architecture",
        "prove",
        "solve",
        "strategy",
        "strategize",
        "decide",
        "devise",
        "figure out",
        "work out",
        "recommend",
    ]
);
lazy_matcher!(
    m_risk_high,
    [
        "auth",
        "authentication",
        "authorization",
        "authorize",
        "password",
        "passwords",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "api key",
        "api keys",
        "payment",
        "payments",
        "billing",
        "production",
        "prod",
        "delete",
        "drop table",
        "migrate",
        "migration",
        "migrations",
        "terraform",
        "kubernetes",
        "deploy",
        "deployment",
        "oauth",
        "oauth2",
        "injection",
        "vulnerable",
        "vulnerability",
        "vulnerabilities",
        "encrypt",
        "encryption",
        "exploit",
        "cve",
        "pii",
        "rotate",
        "hashing",
        "salting",
    ]
);
lazy_matcher!(
    m_risk_medium,
    [
        "database",
        "config",
        "configuration",
        "user data",
        "schema",
        "env var",
        "upgrade",
        "dependency",
        "dependencies",
        "validation",
        "webhook",
        "rate limit",
        "rate limiting",
        "security",
        "permission",
        "permissions",
    ]
);
lazy_matcher!(
    m_trivial,
    ["one-liner", "oneliner", "single line", "trivial"]
);
lazy_matcher!(
    m_complex,
    [
        "refactor",
        "redesign",
        "overhaul",
        "architecture",
        "architect",
        "end-to-end",
        "entire",
        "across",
        "migrate",
        "migration",
        "multi-tenant",
        "scalable",
        "distributed",
        "real-time",
        "zero-downtime",
        "event-driven",
    ]
);
lazy_matcher!(
    m_snippet,
    [
        "function",
        "regex",
        "one-liner",
        "oneliner",
        "snippet",
        "algorithm",
        "query"
    ]
);
lazy_matcher!(
    m_vision,
    [
        "screenshot",
        "photo",
        "diagram",
        "mockup",
        "picture",
        "image of"
    ]
);
lazy_matcher!(
    m_web,
    [
        "search the web",
        "browse",
        "latest news",
        "look up online",
        "google for",
        "web search"
    ]
);

fn shell_wb() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| {
        Regex::new(
            r"(?i)\b(run|runs|execute|install|build|rebuild|deploy|provision|compile|test|tests|migrate|rollback|roll back|back up|backup|apply|rename|train|ingest|stand up|spin up|set up)\b",
        )
        .unwrap()
    })
}

fn test_re() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)\btests?\b").unwrap())
}

fn token_re() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)(\d+)\s*k[\s-]*token").unwrap())
}

fn token_plain_re() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)(\d{4,})[\s-]*token").unwrap())
}

fn quantified_context_re() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| {
        Regex::new(
            r"(?i)\b(\d[\d,]*)[\s-]*(pages?|source\s+files?|files?|documents?|records?|artifacts?|entries|rows?|partitions?)\b",
        )
        .unwrap()
    })
}

fn m_document_report() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| matcher(&["document", "report", "filing", "book", "transcript", "pdf"]))
}

fn m_data_or_table() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| matcher(&["csv", "json", "table of", "spreadsheet"]))
}

fn m_plan_words() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| matcher(&["plan", "roadmap", "design doc"]))
}

lazy_matcher!(
    m_existing_code,
    [
        "codebase",
        "repo",
        "repository",
        "module",
        "files",
        "project",
        "system",
        "endpoint",
        "endpoints",
        "package",
        "service",
        "microservice",
        "middleware",
        "controller",
        "handler",
        "webhook",
        "worker",
        "parser",
        "api",
        "migration",
        "pull request",
        "test coverage",
        "coverage",
        "the auth",
        "the payment",
    ]
);
lazy_matcher!(
    m_review_existing,
    ["review", "audit", "investigate", "refactor", "migrate"]
);
lazy_matcher!(
    m_data_pipeline,
    [
        "pipeline",
        "etl",
        "ingestion",
        "warehouse",
        "retrieval",
        "vector database",
        "vector db",
        "data validation"
    ]
);
lazy_matcher!(
    m_existing_context,
    [
        "existing",
        "current",
        "already",
        "in use",
        "used by",
        "without changing",
        "intermittent failures",
        "cause of",
        "handbook",
        "subsystem",
        "application",
        "data flow",
    ]
);
lazy_matcher!(
    m_conceptual_context,
    [
        "explain",
        "what makes",
        "describe",
        "outline",
        "purpose of",
        "workflow",
        "define"
    ]
);
lazy_matcher!(
    m_large_context,
    [
        "entire corpus",
        "full corpus",
        "monorepo snapshot",
        "repository snapshot",
        "across the entire"
    ]
);
lazy_matcher!(
    m_act_on_existing,
    [
        "inspect",
        "examine",
        "diagnose",
        "trace",
        "track down",
        "profile",
        "harden",
        "modernize",
        "port",
        "untangle",
        "reconcile",
        "evaluate",
        "assess",
        "characterize",
        "walk through",
        "step through",
        "reconstruct",
        "debug",
        "optimize",
        "look into",
        "figure out",
        "find the cause",
        "root cause",
        "map out",
    ]
);

fn definite_existing_re() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| {
        let artifact_noun = r"(?:codebase|repo|repository|module|files?|project|system|subsystem|endpoints?|package|service|microservice|middleware|controller|handler|webhook|worker|parser|pipeline|scheduler|runner|library|client|lifecycle|flow|sequence|implementation|integration|migration|schema|configuration|deployment|dashboard|handbook|specification|document|codepath|tests?|suite)";
        let pattern = format!(
            r"(?i)\b(?:the|its|this|these|those|our|their)\s+(?:\w+\s+){{0,3}}{artifact_noun}\b"
        );
        Regex::new(&pattern).unwrap()
    })
}

fn hit(rx: &Regex, text: &str) -> bool {
    rx.is_match(text)
}

fn is_documentation(text: &str) -> bool {
    let stripped = text.replace("docstring", "");
    hit(m_doc_artifacts(), &stripped) || hit(m_doc_verbs(), &stripped)
}

fn is_software_build(text: &str) -> bool {
    if hit(m_software_domain(), text) {
        return true;
    }
    hit(m_build_verbs(), text) && hit(m_component_nouns(), text)
}

fn has_component(text: &str) -> bool {
    hit(m_component_nouns(), text)
}

fn is_component_coding(text: &str) -> bool {
    hit(m_action_verbs(), text) && has_component(text)
}

fn task_type(text: &str, is_build: bool) -> TaskType {
    if hit(m_summarize(), text) {
        return TaskType::Summarization;
    }
    if is_build {
        return TaskType::Coding;
    }
    if is_documentation(text) {
        return TaskType::Writing;
    }
    if hit(m_writing(), text) {
        return TaskType::Writing;
    }
    if is_component_coding(text) {
        return TaskType::Coding;
    }
    if hit(m_analysis(), text) {
        return TaskType::Analysis;
    }
    if hit(m_reasoning(), text) {
        return TaskType::Reasoning;
    }
    if hit(m_coding(), text) {
        return TaskType::Coding;
    }
    TaskType::General
}

fn risk(text: &str) -> Level {
    if hit(m_risk_high(), text) {
        return Level::High;
    }
    if hit(m_risk_medium(), text) {
        return Level::Medium;
    }
    Level::Low
}

fn complexity(text: &str, task: TaskType, is_build: bool) -> Level {
    if hit(m_trivial(), text) {
        return Level::Low;
    }
    let words = text.split_whitespace().count();
    let complex_hits = m_complex().find_iter(text).count();
    let mut signals = 0;
    if complex_hits >= 1 {
        signals += 1;
    }
    if complex_hits >= 2 {
        signals += 1;
    }
    if is_build {
        signals += 1;
    }
    if text.contains(" and ") && task == TaskType::Coding {
        signals += 1;
    }
    if words > 25 {
        signals += 1;
    }
    if m_software_domain().find_iter(text).count() >= 2 {
        signals += 1;
    }
    if task == TaskType::Reasoning && words >= 6 {
        signals += 1;
    }
    if task == TaskType::Analysis && words >= 7 {
        signals += 1;
    }
    if signals >= 2 {
        Level::High
    } else if signals == 1 {
        Level::Medium
    } else {
        Level::Low
    }
}

fn context_tokens(text: &str, task: TaskType) -> u32 {
    if let Some(m) = token_re().captures(text) {
        let n: u32 = m[1].parse().unwrap_or(0);
        return n * 1000;
    }
    if let Some(m) = token_plain_re().captures(text) {
        return m[1].parse().unwrap_or(0);
    }
    if let Some(m) = quantified_context_re().captures(text) {
        let amount: u64 = m[1].replace(',', "").parse().unwrap_or(0);
        let unit = m[2].to_lowercase();
        if (unit.contains("page") || unit.contains("file") || unit.contains("document"))
            && amount >= 250
        {
            return 100_000;
        }
        if amount >= 50_000 {
            return 100_000;
        }
    }
    if hit(m_large_context(), text) {
        return 100_000;
    }
    if hit(m_document_report(), text) {
        return 30000;
    }
    let existing_context = hit(m_existing_context(), text);
    if hit(m_conceptual_context(), text) && !existing_context {
        return 2000;
    }
    if existing_context
        || hit(m_review_existing(), text)
        || hit(m_act_on_existing(), text)
        || hit(m_data_pipeline(), text)
    {
        return 12000;
    }
    if definite_existing_re().is_match(text) && !hit(m_conceptual_context(), text) {
        return 12000;
    }
    if hit(m_existing_code(), text)
        && matches!(
            task,
            TaskType::Coding | TaskType::Analysis | TaskType::Summarization
        )
    {
        return 12000;
    }
    2000
}

fn band(tokens: u32) -> ContextBand {
    if tokens < 8_000 {
        ContextBand::Small
    } else if tokens < 64_000 {
        ContextBand::Medium
    } else {
        ContextBand::Large
    }
}

/// `_resolve_context` minus the learned-model branch (dead in Python today
/// since `_USE_LEARNED_BAND = False`) — explicit `context_tokens` always
/// wins, otherwise the rule estimator runs.
fn resolve_context(
    text: &str,
    task: TaskType,
    context_tokens_override: Option<u32>,
) -> (u32, ContextBand) {
    if let Some(t) = context_tokens_override {
        return (t, band(t));
    }
    let tokens = context_tokens(text, task);
    (tokens, band(tokens))
}

fn output_type(text: &str, task: TaskType) -> OutputType {
    if task == TaskType::Coding && test_re().is_match(text) {
        return OutputType::CodeTests;
    }
    if task == TaskType::Coding {
        return OutputType::Code;
    }
    if hit(m_data_or_table(), text) {
        return OutputType::Data;
    }
    if task == TaskType::Reasoning || hit(m_plan_words(), text) {
        return OutputType::Plan;
    }
    OutputType::Text
}

fn is_pure_snippet(text: &str, is_build: bool) -> bool {
    hit(m_snippet(), text) && !is_build && !has_component(text)
}

fn tool_needs(text: &str, task: TaskType, is_build: bool) -> Vec<String> {
    let mut needs = Vec::new();
    if task == TaskType::Coding {
        let wants_edit = is_build || has_component(text) || hit(m_action_verbs(), text);
        if wants_edit && !is_pure_snippet(text, is_build) {
            needs.push("file-edit".to_string());
        }
        if hit(m_project_nouns(), text) || shell_wb().is_match(text) {
            needs.push("shell".to_string());
        }
    }
    if hit(m_vision(), text) {
        needs.push("vision".to_string());
    }
    if hit(m_web(), text) {
        needs.push("web".to_string());
    }
    needs
}

fn approval_for(risk: Level) -> ApprovalLevel {
    match risk {
        Level::Low => ApprovalLevel::Auto,
        Level::Medium => ApprovalLevel::Notify,
        Level::High => ApprovalLevel::HumanApprovalRequired,
    }
}

/// Below this task-type confidence, route abstains (asks to clarify).
pub const DEFAULT_UNCERTAINTY_THRESHOLD: f64 = 0.4;

fn task_type_families(text: &str, is_build: bool) -> Vec<TaskType> {
    let mut fams = Vec::new();
    if hit(m_summarize(), text) {
        fams.push(TaskType::Summarization);
    }
    if is_build || is_component_coding(text) || hit(m_coding(), text) {
        fams.push(TaskType::Coding);
    }
    if is_documentation(text) || hit(m_writing(), text) {
        fams.push(TaskType::Writing);
    }
    if hit(m_analysis(), text) {
        fams.push(TaskType::Analysis);
    }
    if hit(m_reasoning(), text) {
        fams.push(TaskType::Reasoning);
    }
    fams
}

fn confidence(
    text: &str,
    task: TaskType,
    is_build: bool,
) -> (f64, Option<TaskType>, Option<String>) {
    let words = text.split_whitespace().count();
    let fams = task_type_families(text, is_build);
    let mut score = 0.5_f64;
    let mut alternative: Option<TaskType> = None;
    let mut reason: Option<String> = None;

    if task == TaskType::General && fams.is_empty() {
        score = 0.25;
        reason = Some("no distinctive task signals matched".to_string());
    } else {
        score += 0.3;
    }

    let distinct: Vec<TaskType> = fams.iter().copied().filter(|f| *f != task).collect();
    if distinct.is_empty() && !fams.is_empty() {
        score += 0.2;
    } else if !distinct.is_empty() {
        score -= 0.15 * distinct.len() as f64;
        alternative = Some(distinct[0]);
        reason = Some(format!("also reads as {}", task_type_value(distinct[0])));
    }

    if words < 3 {
        score -= 0.25;
        if reason.is_none() {
            reason = Some("task description is very short".to_string());
        }
    }

    score = (score * 100.0).round() / 100.0;
    score = score.clamp(0.0, 1.0);
    (score, alternative, reason)
}

/// Matches `TaskType`'s Python `str, Enum` values exactly — used only to
/// build the `ambiguity_reason` message text, not for serde (that's
/// `agentrouter_core::TaskType`'s own `Serialize` impl).
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

/// Mirrors `agentrouter.classifier.classify`'s keyword overrides.
#[derive(Debug, Default, Clone)]
pub struct ClassifyOptions {
    pub context_tokens: Option<u32>,
    pub risk: Option<Level>,
    pub tools: Option<Vec<String>>,
    pub uncertainty_threshold: Option<f64>,
}

pub fn classify(task: &str, opts: &ClassifyOptions) -> Classification {
    let text = task.to_lowercase();
    let is_build = is_software_build(&text);
    let ttype = task_type(&text, is_build);
    let resolved_risk = opts.risk.unwrap_or_else(|| risk(&text));
    let (tokens, ctx_band) = resolve_context(&text, ttype, opts.context_tokens);
    let (conf, alternative, ambiguity) = confidence(&text, ttype, is_build);
    let threshold = opts
        .uncertainty_threshold
        .unwrap_or(DEFAULT_UNCERTAINTY_THRESHOLD);

    Classification {
        task_type: ttype,
        complexity: complexity(&text, ttype, is_build),
        risk: resolved_risk,
        context_tokens: tokens,
        context_band: ctx_band,
        output_type: output_type(&text, ttype),
        tool_needs: opts
            .tools
            .clone()
            .unwrap_or_else(|| tool_needs(&text, ttype, is_build)),
        approval_level: approval_for(resolved_risk),
        confidence: conf,
        needs_clarification: conf < threshold,
        alternative_task_type: alternative,
        ambiguity_reason: ambiguity,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn classify_default(task: &str) -> Classification {
        classify(task, &ClassifyOptions::default())
    }

    #[test]
    fn refactor_payment_module_with_tests() {
        let c = classify_default("Refactor the payment module and add unit tests");
        assert_eq!(c.task_type, TaskType::Coding);
        assert_eq!(c.complexity, Level::High);
        assert_eq!(c.risk, Level::High);
        assert_eq!(c.output_type, OutputType::CodeTests);
        let mut needs = c.tool_needs.clone();
        needs.sort();
        assert_eq!(needs, vec!["file-edit".to_string(), "shell".to_string()]);
    }

    #[test]
    fn write_a_sales_guide_is_writing() {
        assert_eq!(
            classify_default("write a sales guide for the sales team").task_type,
            TaskType::Writing
        );
    }

    #[test]
    fn build_a_sales_guide_app_is_coding() {
        assert_eq!(
            classify_default("build a sales guide app").task_type,
            TaskType::Coding
        );
    }

    #[test]
    fn rewrite_paragraph_is_writing_not_rag() {
        // Regression: substring match used to fire "rag" inside "paragraph".
        assert_eq!(
            classify_default("Rewrite this paragraph to be more concise").task_type,
            TaskType::Writing
        );
    }

    #[test]
    fn docstring_does_not_trigger_documentation_type() {
        let c = classify_default("Add docstrings to every function in this module");
        assert_eq!(c.task_type, TaskType::Coding);
    }

    #[test]
    fn trivial_one_liner_is_low_complexity() {
        let c = classify_default("write a one-liner regex for emails");
        assert_eq!(c.complexity, Level::Low);
    }

    #[test]
    fn high_risk_auth_keyword() {
        assert_eq!(
            classify_default("rotate the production database credentials").risk,
            Level::High
        );
    }

    #[test]
    fn needs_clarification_below_threshold() {
        let c = classify_default("hi");
        assert!(c.needs_clarification);
    }
}
