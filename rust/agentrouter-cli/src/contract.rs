//! Deterministic OpenAPI JSON canonicalization shared with `agentrouter.contract`.
//!
//! Rust contract-tooling slices for canonicalization, reference validation,
//! stable serialization, and trusted-baseline loading. Semantic compatibility
//! classification and safe artifact export remain Python-owned until their
//! complete contracts are ported and differentially checked. The surface-only
//! diff below intentionally omits parameter, schema, and media-type analysis;
//! it must not be used as the compatibility gate.

use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::fmt;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};

const ORDER_INSENSITIVE: &[&str] = &["required", "enum", "tags"];
const MAX_EXPANDED_NODES: usize = 200_000;
const MAX_SCHEMA_COMPARE_DEPTH: usize = 128;
const CONTRACT_VERSION: &str = "v1";
const CONTRACT_EXPORT_COMMAND: &str = "agentrouter contract export";
const HTTP_METHODS: &[&str] = &[
    "get", "put", "post", "delete", "patch", "head", "options", "trace",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BaselineErrorKind {
    Missing,
    Unreadable,
    TooDeep,
    NotOpenApi,
    InvalidReferences,
    TooLarge,
}

impl BaselineErrorKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Missing => "missing",
            Self::Unreadable => "unreadable",
            Self::TooDeep => "too_deep",
            Self::NotOpenApi => "not_openapi",
            Self::InvalidReferences => "invalid_references",
            Self::TooLarge => "too_large",
        }
    }
}

#[derive(Debug)]
pub struct BaselineError {
    pub kind: BaselineErrorKind,
    message: String,
}

impl BaselineError {
    fn new(kind: BaselineErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }
}

impl fmt::Display for BaselineError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for BaselineError {}

/// Return the committed OpenAPI artifact path for a repository root.
pub fn baseline_path(root: &Path) -> PathBuf {
    root.join("contracts")
        .join("http")
        .join(CONTRACT_VERSION)
        .join("openapi.json")
}

/// Read and validate the committed OpenAPI baseline. Missing, malformed,
/// structurally invalid, oversized, or untrusted files always fail closed.
pub fn load_baseline_file(path: &Path) -> Result<Value, BaselineError> {
    let text = match fs::read_to_string(path) {
        Ok(text) => text,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Err(BaselineError::new(
                BaselineErrorKind::Missing,
                format!(
                    "no committed contract at {}; run `{CONTRACT_EXPORT_COMMAND}` and commit it",
                    path.display()
                ),
            ));
        }
        Err(error) => {
            return Err(BaselineError::new(
                BaselineErrorKind::Unreadable,
                format!("{}: unreadable contract: {error}", path.display()),
            ));
        }
    };
    let document: Value = serde_json::from_str(&text).map_err(|error| {
        let kind = if error.to_string().contains("recursion limit exceeded") {
            BaselineErrorKind::TooDeep
        } else {
            BaselineErrorKind::Unreadable
        };
        let message = if kind == BaselineErrorKind::TooDeep {
            format!("{}: nested too deeply to parse safely", path.display())
        } else {
            format!("{}: unreadable contract: {error}", path.display())
        };
        BaselineError::new(kind, message)
    })?;
    if !document.is_object() || document.get("paths").is_none() {
        return Err(BaselineError::new(
            BaselineErrorKind::NotOpenApi,
            format!("{}: not an OpenAPI document (no 'paths')", path.display()),
        ));
    }
    let invalid = validate_refs(&document)
        .map_err(|error| BaselineError::new(BaselineErrorKind::TooLarge, error))?;
    if !invalid.is_empty() {
        let details = invalid
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join(", ");
        return Err(BaselineError::new(
            BaselineErrorKind::InvalidReferences,
            format!(
                "{}: {} unusable $ref(s) — the contract cannot be trusted as a baseline: {details}",
                path.display(),
                invalid.len()
            ),
        ));
    }
    Ok(document)
}

/// Load the committed OpenAPI baseline under a repository root.
pub fn load_baseline(root: &Path) -> Result<Value, BaselineError> {
    load_baseline_file(&baseline_path(root))
}

/// Compare the OpenAPI document and operation surface while the complete
/// schema, parameter, and media-type analyzer is being ported. Results use the
/// same report shape and change ordering as Python's checker.
pub fn diff_contracts_surface(old: &Value, new: &Value) -> Result<Value, String> {
    let mut changes = Vec::<SurfaceChange>::new();
    let mut schema_budget = MAX_EXPANDED_NODES;
    let old_version = python_object_field(old, "info", "version");
    let new_version = python_object_field(new, "info", "version");
    if !python_value_equal(old_version, new_version) {
        add_surface_change(
            &mut changes,
            "risky",
            "api_version_changed",
            "info.version",
            format!(
                "{} -> {}",
                python_display(old_version),
                python_display(new_version)
            ),
        );
    }

    diff_security_schemes(old, new, &mut changes);
    if !python_or_empty_equal(old.get("servers"), new.get("servers")) {
        add_surface_change(
            &mut changes,
            "breaking",
            "servers_changed",
            "servers",
            format!(
                "{} -> {} (every URL moves)",
                python_display(old.get("servers")),
                python_display(new.get("servers"))
            ),
        );
    }

    let old_paths = object_or_empty(old.get("paths"));
    let new_paths = object_or_empty(new.get("paths"));
    let old_path_names = old_paths.keys().cloned().collect::<BTreeSet<_>>();
    let new_path_names = new_paths.keys().cloned().collect::<BTreeSet<_>>();

    for path in old_path_names.difference(&new_path_names) {
        add_surface_change(
            &mut changes,
            "breaking",
            "endpoint_removed",
            path,
            "path no longer served",
        );
    }
    for path in new_path_names.difference(&old_path_names) {
        add_surface_change(&mut changes, "additive", "endpoint_added", path, "new path");
    }

    for path in old_path_names.intersection(&new_path_names) {
        let old_operations = object_or_empty(old_paths.get(path));
        let new_operations = object_or_empty(new_paths.get(path));
        let old_methods = old_operations.keys().cloned().collect::<BTreeSet<_>>();
        let new_methods = new_operations.keys().cloned().collect::<BTreeSet<_>>();
        for method in old_methods.difference(&new_methods) {
            if HTTP_METHODS.contains(&method.as_str()) {
                add_surface_change(
                    &mut changes,
                    "breaking",
                    "method_removed",
                    format!("{path}.{method}"),
                    "method no longer served",
                );
            }
        }
        for method in new_methods.difference(&old_methods) {
            if HTTP_METHODS.contains(&method.as_str()) {
                add_surface_change(
                    &mut changes,
                    "additive",
                    "method_added",
                    format!("{path}.{method}"),
                    "new method",
                );
            }
        }

        for method in old_methods.intersection(&new_methods) {
            if !HTTP_METHODS.contains(&method.as_str()) {
                continue;
            }
            let location = format!("{path}.{method}");
            let old_operation = object_or_empty(old_operations.get(method));
            let new_operation = object_or_empty(new_operations.get(method));

            diff_operation_security(
                old_operation,
                new_operation,
                old,
                new,
                &location,
                &mut changes,
            );
            diff_parameters(old_operation, new_operation, &location, &mut changes);

            let old_id = old_operation.get("operationId");
            let new_id = new_operation.get("operationId");
            if !python_value_equal(old_id, new_id) {
                add_surface_change(
                    &mut changes,
                    "risky",
                    "operation_id_changed",
                    &location,
                    format!(
                        "{} -> {} (renames the method in generated clients)",
                        python_display(old_id),
                        python_display(new_id)
                    ),
                );
            }

            let was_deprecated = old_operation.get("deprecated").is_some_and(python_truthy);
            let is_deprecated = new_operation.get("deprecated").is_some_and(python_truthy);
            if was_deprecated != is_deprecated {
                add_surface_change(
                    &mut changes,
                    "risky",
                    "deprecation_changed",
                    &location,
                    format!(
                        "deprecated: {} -> {}",
                        python_bool_display(was_deprecated),
                        python_bool_display(is_deprecated)
                    ),
                );
            }

            let old_required = request_body_required(old_operation.get("requestBody"));
            let new_required = request_body_required(new_operation.get("requestBody"));
            if old_required != new_required {
                add_surface_change(
                    &mut changes,
                    if new_required { "breaking" } else { "additive" },
                    if new_required {
                        "request_body_became_required"
                    } else {
                        "request_body_became_optional"
                    },
                    format!("{location}.request"),
                    format!(
                        "required: {} -> {}",
                        python_bool_display(old_required),
                        python_bool_display(new_required)
                    ),
                );
            }

            diff_media_types(
                old_operation.get("requestBody"),
                new_operation.get("requestBody"),
                &format!("{location}.request"),
                &mut changes,
            );
            diff_content_schema(
                old_operation.get("requestBody"),
                new_operation.get("requestBody"),
                &format!("{location}.request"),
                true,
                &mut schema_budget,
                &mut changes,
            )?;

            let old_responses = object_or_empty(old_operation.get("responses"));
            let new_responses = object_or_empty(new_operation.get("responses"));
            let old_statuses = old_responses.keys().cloned().collect::<BTreeSet<_>>();
            let new_statuses = new_responses.keys().cloned().collect::<BTreeSet<_>>();
            for status in old_statuses.difference(&new_statuses) {
                if status_still_covered(status, &new_statuses) {
                    add_surface_change(
                        &mut changes,
                        "risky",
                        "response_status_refined",
                        format!("{location}.{status}"),
                        "replaced by explicit codes in the same class",
                    );
                    continue;
                }
                add_surface_change(
                    &mut changes,
                    "breaking",
                    "response_status_removed",
                    format!("{location}.{status}"),
                    "status no longer documented",
                );
            }
            for status in new_statuses.difference(&old_statuses) {
                add_surface_change(
                    &mut changes,
                    "additive",
                    "response_status_added",
                    format!("{location}.{status}"),
                    "newly documented status",
                );
            }
            for status in old_statuses.intersection(&new_statuses) {
                diff_media_types(
                    old_responses.get(status),
                    new_responses.get(status),
                    &format!("{location}.{status}"),
                    &mut changes,
                );
                diff_content_schema(
                    old_responses.get(status),
                    new_responses.get(status),
                    &format!("{location}.{status}"),
                    false,
                    &mut schema_budget,
                    &mut changes,
                )?;
            }

            if !python_or_empty_equal(old_operation.get("summary"), new_operation.get("summary"))
                || !python_or_empty_equal(
                    old_operation.get("description"),
                    new_operation.get("description"),
                )
            {
                add_surface_change(
                    &mut changes,
                    "risky",
                    "documented_semantics_changed",
                    &location,
                    "summary/description changed",
                );
            }
        }
    }

    changes.sort_by(|left, right| {
        severity_rank(&left.severity)
            .cmp(&severity_rank(&right.severity))
            .then_with(|| left.location.cmp(&right.location))
            .then_with(|| left.kind.cmp(&right.kind))
    });
    let breaking = changes
        .iter()
        .filter(|change| change.severity == "breaking")
        .count();
    let accepted = changes
        .iter()
        .filter(|change| change.severity == "accepted")
        .count();
    let risky = changes
        .iter()
        .filter(|change| change.severity == "risky")
        .count();
    let additive = changes
        .iter()
        .filter(|change| change.severity == "additive")
        .count();
    Ok(json!({
        "compatible": breaking == 0,
        "counts": {
            "breaking": breaking,
            "accepted": accepted,
            "risky": risky,
            "additive": additive,
        },
        "changes": changes,
    }))
}

#[derive(serde::Serialize)]
struct SurfaceChange {
    severity: String,
    kind: String,
    location: String,
    detail: String,
}

fn add_surface_change(
    changes: &mut Vec<SurfaceChange>,
    severity: &str,
    kind: &str,
    location: impl Into<String>,
    detail: impl Into<String>,
) {
    changes.push(SurfaceChange {
        severity: severity.to_owned(),
        kind: kind.to_owned(),
        location: location.into(),
        detail: detail.into(),
    });
}

fn severity_rank(severity: &str) -> usize {
    match severity {
        "breaking" => 0,
        "accepted" => 1,
        "risky" => 2,
        _ => 3,
    }
}

fn object_or_empty(value: Option<&Value>) -> &Map<String, Value> {
    static EMPTY: std::sync::OnceLock<Map<String, Value>> = std::sync::OnceLock::new();
    value
        .and_then(Value::as_object)
        .unwrap_or_else(|| EMPTY.get_or_init(Map::new))
}

fn python_object_field<'a>(document: &'a Value, outer: &str, inner: &str) -> Option<&'a Value> {
    document
        .get(outer)
        .filter(|value| python_truthy(value))
        .and_then(Value::as_object)
        .and_then(|object| object.get(inner))
}

fn python_value_equal(left: Option<&Value>, right: Option<&Value>) -> bool {
    match (
        left.filter(|value| !value.is_null()),
        right.filter(|value| !value.is_null()),
    ) {
        (None, None) => true,
        (Some(left), Some(right)) => left == right,
        _ => false,
    }
}

fn python_or_empty_equal(left: Option<&Value>, right: Option<&Value>) -> bool {
    let left = left.filter(|value| python_truthy(value));
    let right = right.filter(|value| python_truthy(value));
    python_value_equal(left, right)
}

fn python_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64() != Some(0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

fn status_still_covered(status: &str, present: &BTreeSet<String>) -> bool {
    if status.len() == 3 && status.to_ascii_uppercase().ends_with("XX") {
        let prefix = status.as_bytes()[0] as char;
        return present.iter().any(|candidate| {
            let bytes = candidate.as_bytes();
            bytes.len() == 3
                && bytes[0] as char == prefix
                && bytes[1..].iter().all(u8::is_ascii_digit)
        });
    }
    if status.len() == 3 && status.bytes().all(|byte| byte.is_ascii_digit()) {
        let class = &status[..1];
        return present.contains(&format!("{class}XX")) || present.contains(&format!("{class}xx"));
    }
    false
}

fn python_display(value: Option<&Value>) -> String {
    match value.filter(|value| !value.is_null()) {
        None => "None".to_owned(),
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(true)) => "True".to_owned(),
        Some(Value::Bool(false)) => "False".to_owned(),
        Some(value @ (Value::Array(_) | Value::Object(_))) => python_repr(value),
        Some(value) => value.to_string(),
    }
}

fn python_bool_display(value: bool) -> &'static str {
    if value {
        "True"
    } else {
        "False"
    }
}

fn request_body_required(value: Option<&Value>) -> bool {
    value
        .and_then(Value::as_object)
        .and_then(|object| object.get("required"))
        .is_some_and(python_truthy)
}

fn diff_parameters(
    old_operation: &Map<String, Value>,
    new_operation: &Map<String, Value>,
    location: &str,
    changes: &mut Vec<SurfaceChange>,
) {
    let before = parameter_index(old_operation);
    let after = parameter_index(new_operation);
    let parameter_location = format!("{location}.parameters");

    for key in before.keys().filter(|key| !after.contains_key(*key)) {
        add_surface_change(
            changes,
            "breaking",
            "parameter_removed",
            format!("{parameter_location}.{}", key.1),
            format!("{} parameter removed", key.0),
        );
    }
    for key in after.keys().filter(|key| !before.contains_key(*key)) {
        let parameter = after[key];
        let required = parameter.get("required").is_some_and(python_truthy);
        add_surface_change(
            changes,
            if required { "breaking" } else { "additive" },
            if required {
                "required_parameter_added"
            } else {
                "optional_parameter_added"
            },
            format!("{parameter_location}.{}", key.1),
            format!("new {} parameter", key.0),
        );
    }
    for key in before.keys().filter(|key| after.contains_key(*key)) {
        let was_required = before[key].get("required").is_some_and(python_truthy);
        let is_required = after[key].get("required").is_some_and(python_truthy);
        if was_required == is_required {
            continue;
        }
        let became_required = is_required;
        add_surface_change(
            changes,
            if became_required {
                "breaking"
            } else {
                "additive"
            },
            if became_required {
                "parameter_became_required"
            } else {
                "parameter_became_optional"
            },
            format!("{parameter_location}.{}", key.1),
            if became_required {
                "optional -> required"
            } else {
                "required -> optional"
            },
        );
    }
}

fn parameter_index(
    operation: &Map<String, Value>,
) -> BTreeMap<(String, String), &Map<String, Value>> {
    operation
        .get("parameters")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|parameter| {
            let object = parameter.as_object()?;
            let name = object.get("name")?;
            let key = (
                object
                    .get("in")
                    .map(|value| python_display(Some(value)))
                    .unwrap_or_else(|| "None".to_owned()),
                python_display(Some(name)),
            );
            Some((key, object))
        })
        .collect()
}

fn diff_media_types(
    old_value: Option<&Value>,
    new_value: Option<&Value>,
    location: &str,
    changes: &mut Vec<SurfaceChange>,
) {
    let before = media_types(old_value);
    let after = media_types(new_value);
    for media in before.difference(&after) {
        add_surface_change(
            changes,
            "breaking",
            "media_type_removed",
            location,
            format!("{media} no longer offered"),
        );
    }
    for media in after.difference(&before) {
        add_surface_change(
            changes,
            "additive",
            "media_type_added",
            location,
            format!("{media} now offered"),
        );
    }
}

fn media_types(value: Option<&Value>) -> BTreeSet<String> {
    value
        .and_then(Value::as_object)
        .and_then(|object| object.get("content"))
        .and_then(Value::as_object)
        .map(|content| content.keys().cloned().collect())
        .unwrap_or_default()
}

fn diff_content_schema(
    old_body: Option<&Value>,
    new_body: Option<&Value>,
    location: &str,
    request: bool,
    budget: &mut usize,
    changes: &mut Vec<SurfaceChange>,
) -> Result<(), String> {
    diff_inline_schema(
        content_schema(old_body),
        content_schema(new_body),
        location,
        request,
        budget,
        0,
        changes,
    )
}

fn content_schema(body: Option<&Value>) -> Option<&Value> {
    let content = body
        .and_then(Value::as_object)
        .and_then(|object| object.get("content"))
        .and_then(Value::as_object)?;
    if let Some(media) = content.get("application/json").and_then(Value::as_object) {
        return media.get("schema");
    }
    content
        .values()
        .filter_map(Value::as_object)
        .find_map(|media| media.get("schema"))
}

fn diff_inline_schema(
    old_value: Option<&Value>,
    new_value: Option<&Value>,
    location: &str,
    request: bool,
    budget: &mut usize,
    depth: usize,
    changes: &mut Vec<SurfaceChange>,
) -> Result<(), String> {
    if *budget == 0 {
        return Err(format!(
            "contract is too large to compare safely (over {MAX_EXPANDED_NODES} schema nodes)"
        ));
    }
    *budget -= 1;
    if depth > MAX_SCHEMA_COMPARE_DEPTH {
        return Err(format!(
            "contract is nested too deeply to compare safely (over {MAX_SCHEMA_COMPARE_DEPTH} schema levels)"
        ));
    }

    let old_schema = match old_value {
        None => empty_object(),
        Some(value) => match value.as_object() {
            Some(schema) => schema,
            None => return Ok(()),
        },
    };
    let new_schema = match new_value {
        None => empty_object(),
        Some(value) => match value.as_object() {
            Some(schema) => schema,
            None => return Ok(()),
        },
    };

    // Reference expansion is a separate bounded operation. Keep referenced
    // schemas out of this inline-only slice until it can share the full
    // document-wide expansion budget and cycle handling.
    if old_schema.contains_key("$ref") || new_schema.contains_key("$ref") {
        return Ok(());
    }

    let old_type = schema_type(old_schema.get("type"));
    let new_type = schema_type(new_schema.get("type"));
    let old_untyped = schema_is_untyped(old_schema);
    let new_untyped = schema_is_untyped(new_schema);
    if old_untyped != new_untyped {
        let erased = new_untyped;
        add_surface_change(
            changes,
            if erased {
                if request {
                    "additive"
                } else {
                    "risky"
                }
            } else if request {
                "breaking"
            } else {
                "risky"
            },
            if erased {
                "type_erased"
            } else {
                "type_declared"
            },
            location,
            if erased {
                "schema no longer constrains the value"
            } else {
                "schema now constrains a previously free value"
            },
        );
        return Ok(());
    }
    if let (Some(old_type), Some(new_type)) = (&old_type, &new_type) {
        if old_type != new_type {
            add_surface_change(
                changes,
                "breaking",
                if request {
                    "request_type_changed"
                } else {
                    "response_type_changed"
                },
                location,
                format!("type {old_type} -> {new_type}"),
            );
        }
    }

    let old_properties = object_or_empty(old_schema.get("properties"));
    let new_properties = object_or_empty(new_schema.get("properties"));
    let old_required = schema_required(old_schema.get("required"));
    let new_required = schema_required(new_schema.get("required"));

    for name in old_properties
        .keys()
        .filter(|name| !new_properties.contains_key(*name))
    {
        let (severity, kind) = if request && old_required.contains(name) {
            ("breaking", "required_request_field_removed")
        } else if request {
            ("risky", "request_field_removed")
        } else {
            ("breaking", "response_field_removed")
        };
        add_surface_change(
            changes,
            severity,
            kind,
            format!("{location}.{name}"),
            "field removed",
        );
    }
    for name in new_properties
        .keys()
        .filter(|name| !old_properties.contains_key(*name))
    {
        let required = new_required.contains(name);
        add_surface_change(
            changes,
            if request && required {
                "breaking"
            } else {
                "additive"
            },
            if request && required {
                "required_request_field_added"
            } else if request {
                "optional_request_field_added"
            } else {
                "response_field_added"
            },
            format!("{location}.{name}"),
            if request && required {
                "new field is required"
            } else if request {
                "new optional field"
            } else {
                "new response field"
            },
        );
    }
    for name in old_properties
        .keys()
        .filter(|name| new_properties.contains_key(*name))
    {
        let was_required = old_required.contains(name);
        let is_required = new_required.contains(name);
        if was_required != is_required {
            let became_required = is_required;
            add_surface_change(
                changes,
                if became_required == request {
                    "breaking"
                } else {
                    "additive"
                },
                if became_required {
                    "field_became_required"
                } else {
                    "field_became_optional"
                },
                format!("{location}.{name}"),
                if became_required {
                    "optional -> required"
                } else {
                    "required -> optional"
                },
            );
        }
        diff_inline_schema(
            old_properties.get(name),
            new_properties.get(name),
            &format!("{location}.{name}"),
            request,
            budget,
            depth + 1,
            changes,
        )?;
    }

    if old_schema.contains_key("items") || new_schema.contains_key("items") {
        diff_inline_schema(
            old_schema.get("items"),
            new_schema.get("items"),
            &format!("{location}[]"),
            request,
            budget,
            depth + 1,
            changes,
        )?;
    }
    Ok(())
}

fn schema_type(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(value) => Some(value.clone()),
        Value::Array(values) => {
            let names = values
                .iter()
                .filter_map(Value::as_str)
                .collect::<BTreeSet<_>>();
            if names.is_empty() {
                None
            } else {
                Some(names.into_iter().collect::<Vec<_>>().join("|"))
            }
        }
        _ => None,
    }
}

fn schema_is_untyped(schema: &Map<String, Value>) -> bool {
    schema.keys().all(|key| {
        matches!(
            key.as_str(),
            "title" | "description" | "default" | "example" | "examples"
        )
    })
}

fn schema_required(value: Option<&Value>) -> BTreeSet<String> {
    value
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_owned)
        .collect()
}

fn diff_operation_security(
    old_operation: &Map<String, Value>,
    new_operation: &Map<String, Value>,
    old_document: &Value,
    new_document: &Value,
    location: &str,
    changes: &mut Vec<SurfaceChange>,
) {
    let before = security_requirements(old_operation, old_document);
    let after = security_requirements(new_operation, new_document);
    if before == after {
        return;
    }

    let removed = before.difference(&after).next().is_some();
    let added = after.difference(&before).next().is_some();
    if removed {
        let unauthenticated = after.is_empty();
        add_surface_change(
            changes,
            "breaking",
            if unauthenticated {
                "authentication_removed"
            } else {
                "authentication_changed"
            },
            location,
            if unauthenticated {
                "endpoint no longer requires authentication"
            } else {
                "alternative removed"
            },
        );
    }
    if added && !removed {
        let was_unauthenticated = before.is_empty();
        add_surface_change(
            changes,
            if was_unauthenticated {
                "breaking"
            } else {
                "additive"
            },
            if was_unauthenticated {
                "authentication_added"
            } else {
                "authentication_alternative_added"
            },
            location,
            if was_unauthenticated {
                "endpoint now requires authentication"
            } else {
                "an additional accepted scheme"
            },
        );
    }
}

fn security_requirements(operation: &Map<String, Value>, document: &Value) -> BTreeSet<String> {
    let requirements = operation
        .get("security")
        .filter(|value| !value.is_null())
        .or_else(|| document.get("security"));
    requirements
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|requirement| {
            if requirement.is_object() {
                serde_json::to_string(requirement).unwrap_or_default()
            } else {
                python_repr(requirement)
            }
        })
        .collect()
}

fn diff_security_schemes(old: &Value, new: &Value, changes: &mut Vec<SurfaceChange>) {
    let old_schemes = security_schemes(old);
    let new_schemes = security_schemes(new);
    let old_names = old_schemes.keys().cloned().collect::<BTreeSet<_>>();
    let new_names = new_schemes.keys().cloned().collect::<BTreeSet<_>>();

    for name in old_names.difference(&new_names) {
        add_surface_change(
            changes,
            "breaking",
            "security_scheme_removed",
            format!("securitySchemes.{name}"),
            "scheme removed",
        );
    }
    for name in new_names.difference(&old_names) {
        add_surface_change(
            changes,
            "additive",
            "security_scheme_added",
            format!("securitySchemes.{name}"),
            "scheme added",
        );
    }

    for name in old_names.intersection(&new_names) {
        let (Some(old_value), Some(new_value)) = (old_schemes.get(name), new_schemes.get(name))
        else {
            continue;
        };
        if !old_value.is_object() || !new_value.is_object() {
            continue;
        }
        let before = object_or_empty(Some(old_value));
        let after = object_or_empty(Some(new_value));
        for attribute in [
            "type",
            "name",
            "in",
            "scheme",
            "bearerFormat",
            "openIdConnectUrl",
            "flows",
        ] {
            let old_value = before.get(attribute);
            let new_value = after.get(attribute);
            if !python_value_equal(old_value, new_value) {
                add_surface_change(
                    changes,
                    "breaking",
                    "security_scheme_changed",
                    format!("securitySchemes.{name}.{attribute}"),
                    format!(
                        "{} -> {}",
                        python_repr_option(old_value),
                        python_repr_option(new_value)
                    ),
                );
            }
        }
    }
}

fn security_schemes(document: &Value) -> &Map<String, Value> {
    document
        .get("components")
        .filter(|value| python_truthy(value))
        .and_then(Value::as_object)
        .and_then(|components| components.get("securitySchemes"))
        .filter(|value| python_truthy(value))
        .and_then(Value::as_object)
        .unwrap_or_else(|| empty_object())
}

fn empty_object() -> &'static Map<String, Value> {
    static EMPTY: std::sync::OnceLock<Map<String, Value>> = std::sync::OnceLock::new();
    EMPTY.get_or_init(Map::new)
}

fn python_repr_option(value: Option<&Value>) -> String {
    value.map_or_else(|| "None".to_owned(), python_repr)
}

fn python_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".to_owned(),
        Value::Bool(value) => python_bool_display(*value).to_owned(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => python_string_repr(value),
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_repr)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!("{}: {}", python_string_repr(key), python_repr(value)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn python_string_repr(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut rendered = String::with_capacity(value.len() + 2);
    rendered.push(quote);
    for character in value.chars() {
        match character {
            '\\' => rendered.push_str("\\\\"),
            '\n' => rendered.push_str("\\n"),
            '\r' => rendered.push_str("\\r"),
            '\t' => rendered.push_str("\\t"),
            character if character == quote => {
                rendered.push('\\');
                rendered.push(character);
            }
            character if character.is_control() => {
                use std::fmt::Write as _;
                let _ = write!(rendered, "\\x{:02x}", character as u32);
            }
            character => rendered.push(character),
        }
    }
    rendered.push(quote);
    rendered
}

/// Recursively normalize object keys and the OpenAPI arrays whose order is not
/// semantically meaningful, matching Python's `contract._canonical` behavior.
pub fn canonicalize(value: &mut Value) {
    match value {
        Value::Object(object) => {
            // serde_json's default object map is key-sorted, just like the
            // canonical Python mapping produced here.
            let mut entries = std::mem::take(object).into_iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            let mut canonical = Map::new();
            for (key, mut child) in entries {
                canonicalize(&mut child);
                if let Value::Array(items) = &mut child {
                    if ORDER_INSENSITIVE.contains(&key.as_str())
                        && items.iter().all(Value::is_string)
                    {
                        items.sort_by(|left, right| left.as_str().cmp(&right.as_str()));
                    } else if matches!(key.as_str(), "anyOf" | "oneOf" | "allOf") {
                        items.sort_by_cached_key(json_sort_key);
                    } else if key == "parameters" {
                        items.sort_by_cached_key(parameter_sort_key);
                    }
                }
                canonical.insert(key, child);
            }
            *object = canonical;
        }
        Value::Array(items) => {
            for child in items {
                canonicalize(child);
            }
        }
        _ => {}
    }
}

/// Serialize JSON with two-space indentation, sorted object keys, literal
/// Unicode, and a final newline, as Python's `contract.dumps` does.
pub fn dumps(value: &Value) -> Result<String, serde_json::Error> {
    let mut sorted = value.clone();
    sort_object_keys(&mut sorted);
    let mut text = serde_json::to_string_pretty(&sorted)?;
    text.push('\n');
    Ok(text)
}

fn sort_object_keys(value: &mut Value) {
    match value {
        Value::Object(object) => {
            let mut entries = std::mem::take(object).into_iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            let mut sorted = Map::new();
            for (key, mut child) in entries {
                sort_object_keys(&mut child);
                sorted.insert(key, child);
            }
            *object = sorted;
        }
        Value::Array(items) => {
            for item in items {
                sort_object_keys(item);
            }
        }
        _ => {}
    }
}

/// Return invalid OpenAPI references in sorted, deduplicated order, matching
/// Python's `contract.validate_refs`. Only local object-key paths are accepted;
/// missing and cyclic references are reported so callers can fail closed.
pub fn validate_refs(document: &Value) -> Result<Vec<String>, String> {
    enum Action<'a> {
        Walk(&'a Value),
        FinishReference(String),
    }

    let mut pending = vec![Action::Walk(document)];
    let mut visiting = HashSet::<String>::new();
    let mut validated = HashSet::<String>::new();
    let mut invalid = BTreeSet::<String>::new();
    let mut remaining = MAX_EXPANDED_NODES;
    let mut scheduled_nodes = 1_usize;

    while let Some(action) = pending.pop() {
        match action {
            Action::FinishReference(reference) => {
                visiting.remove(&reference);
                validated.insert(reference);
            }
            Action::Walk(node) => {
                remaining = remaining.saturating_sub(1);
                if remaining == 0 {
                    return Err(format!(
                        "contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it"
                    ));
                }

                match node {
                    Value::Array(items) => {
                        schedule_nodes(&mut scheduled_nodes, items.len())?;
                        pending.extend(items.iter().rev().map(Action::Walk));
                    }
                    Value::Object(object) => {
                        if let Some(reference) = object.get("$ref").and_then(Value::as_str) {
                            if !reference.starts_with("#/") {
                                invalid
                                    .insert(format!("{reference} (only local refs are supported)"));
                                continue;
                            }
                            if visiting.contains(reference) {
                                invalid.insert(format!("{reference} (self-referential)"));
                                continue;
                            }
                            if validated.contains(reference) {
                                continue;
                            }
                            let Some(target) = resolve_local_reference(document, reference) else {
                                invalid.insert(format!("{reference} (unresolvable)"));
                                continue;
                            };
                            schedule_nodes(&mut scheduled_nodes, 1)?;
                            visiting.insert(reference.to_owned());
                            pending.push(Action::FinishReference(reference.to_owned()));
                            pending.push(Action::Walk(target));
                        } else {
                            let mut children = object.values().collect::<Vec<_>>();
                            children.reverse();
                            schedule_nodes(&mut scheduled_nodes, children.len())?;
                            pending.extend(children.into_iter().map(Action::Walk));
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(invalid.into_iter().collect())
}

fn schedule_nodes(scheduled: &mut usize, additional: usize) -> Result<(), String> {
    let Some(total) = scheduled.checked_add(additional) else {
        return Err(node_budget_error());
    };
    // Python's walker errors when its 200,000th node is visited, so a valid
    // document can contain at most 199,999 walked nodes including the root.
    if total >= MAX_EXPANDED_NODES {
        return Err(node_budget_error());
    }
    *scheduled = total;
    Ok(())
}

fn node_budget_error() -> String {
    format!("contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it")
}

fn resolve_local_reference<'a>(document: &'a Value, reference: &str) -> Option<&'a Value> {
    let mut target = document;
    for part in reference.strip_prefix("#/")?.split('/') {
        target = target.as_object()?.get(part)?;
    }
    Some(target)
}

fn json_sort_key(value: &Value) -> String {
    // Python uses `json.dumps(value, sort_keys=True)` with ensure_ascii enabled
    // and the default comma/colon spacing. Reproduce that text so Unicode
    // branch values sort in precisely the same order on every platform.
    match value {
        Value::Null => "null".to_owned(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => python_json_string(value),
        Value::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(json_sort_key)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(object) => {
            let mut entries = object.iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(right.0));
            format!(
                "{{{}}}",
                entries
                    .into_iter()
                    .map(|(key, value)| format!(
                        "{}: {}",
                        python_json_string(key),
                        json_sort_key(value)
                    ))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
    }
}

fn python_json_string(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\u{0008}' => output.push_str("\\b"),
            '\u{000c}' => output.push_str("\\f"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            '\u{0000}'..='\u{001f}' => {
                let _ = write!(output, "\\u{:04x}", character as u32);
            }
            '\u{007f}'..='\u{ffff}' => {
                let _ = write!(output, "\\u{:04x}", character as u32);
            }
            '\u{10000}'..='\u{10ffff}' => {
                let code = character as u32 - 0x1_0000;
                let high = 0xd800 + (code >> 10);
                let low = 0xdc00 + (code & 0x3ff);
                let _ = write!(output, "\\u{high:04x}\\u{low:04x}");
            }
            _ => output.push(character),
        }
    }
    output.push('"');
    output
}

fn parameter_sort_key(value: &Value) -> (String, String) {
    let Some(object) = value.as_object() else {
        return (String::new(), String::new());
    };
    (
        python_string(object.get("in")),
        python_string(object.get("name")),
    )
}

fn python_string(value: Option<&Value>) -> String {
    match value {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => if *value { "True" } else { "False" }.to_owned(),
        Some(value) => value.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonicalizes_semantic_lists_and_preserves_other_array_order() {
        let mut value = json!({
            "z": 1,
            "tags": ["z", "a"],
            "required": ["z", "a"],
            "enum": ["z", "a"],
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "parameters": [
                {"name": "z", "in": "query"},
                {"name": "a", "in": "path"}
            ],
            "examples": ["z", "a"]
        });
        canonicalize(&mut value);
        assert_eq!(value["required"], json!(["a", "z"]));
        assert_eq!(value["enum"], json!(["a", "z"]));
        assert_eq!(value["tags"], json!(["a", "z"]));
        assert_eq!(value["anyOf"][0]["type"], "null");
        assert_eq!(value["parameters"][0]["name"], "a");
        assert_eq!(value["examples"], json!(["z", "a"]));
        assert_eq!(value.as_object().unwrap().keys().next().unwrap(), "anyOf");
    }

    #[test]
    fn schema_branch_sort_key_matches_python_ascii_escaping() {
        let mut value = json!({"anyOf": [{"const": "z"}, {"const": "é"}]});
        canonicalize(&mut value);
        assert_eq!(value["anyOf"][0]["const"], "é");
    }

    #[test]
    fn dumps_has_python_compatible_indentation_unicode_and_newline() {
        let value = json!({"name": "AgentRouter 🧭", "nested": {"value": true}});
        assert_eq!(
            dumps(&value).unwrap(),
            "{\n  \"name\": \"AgentRouter 🧭\",\n  \"nested\": {\n    \"value\": true\n  }\n}\n"
        );
    }

    #[test]
    fn dumps_sorts_keys_without_reordering_arrays() {
        let value = json!({"z": [2, 1], "a": 0});
        assert_eq!(
            dumps(&value).unwrap(),
            "{\n  \"a\": 0,\n  \"z\": [\n    2,\n    1\n  ]\n}\n"
        );
    }

    #[test]
    fn reference_validation_reports_missing_external_and_cyclic_targets() {
        let document = json!({
            "components": {"schemas": {
                "A": {"$ref": "#/components/schemas/B"},
                "B": {"$ref": "#/components/schemas/A"}
            }},
            "paths": {"/x": {"get": {
                "responses": {"200": {"schema": {"$ref": "#/components/schemas/Missing"}}},
                "parameters": [{"schema": {"$ref": "https://example.test/schema.json"}}]
            }}}
        });
        let invalid = validate_refs(&document).unwrap();
        assert_eq!(invalid.len(), 3);
        assert!(invalid.iter().any(|item| item.contains("only local refs")));
        assert!(invalid.iter().any(|item| item.contains("unresolvable")));
        assert!(invalid.iter().any(|item| item.contains("self-referential")));
        assert!(invalid.windows(2).all(|pair| pair[0] < pair[1]));
    }

    #[test]
    fn reference_validation_has_a_bounded_node_budget() {
        let document = Value::Array(vec![Value::Null; MAX_EXPANDED_NODES]);
        assert_eq!(
            validate_refs(&document).unwrap_err(),
            format!("contract has more than {MAX_EXPANDED_NODES} nodes; refusing to validate it")
        );
    }
}
