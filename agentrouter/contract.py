"""Versioned HTTP contract: deterministic OpenAPI export + semantic compatibility check.

The REST surface is a product contract, so it is exported to a committed,
byte-stable artifact and every change is classified before it can land:

* ``canonical_openapi`` renders the *real* FastAPI app and normalises it —
  recursive key sort, order-insensitive lists sorted, environment-dependent
  fields dropped — so re-running it on an unchanged app is byte-identical.
* ``diff_contracts`` compares a baseline against the current document and
  classifies every difference as **breaking**, **risky** or **additive**,
  resolving ``$ref`` so schema changes are compared structurally rather than by
  reference name.

Split of responsibilities between the two committed files:

* ``openapi.json`` is *the contract*. It contains no timestamp and no commit, so
  it changes only when the API actually changes, and it is the only file the
  compatibility check compares.
* ``manifest.json`` carries provenance (product version, tool, source commit,
  generation time). It deliberately sits outside the comparison — pinning a
  commit or a timestamp inside the contract itself would make every regeneration
  a diff and destroy the signal the checker exists to provide.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

CONTRACT_VERSION = "v1"
CONTRACT_DIR = Path("contracts") / "http" / CONTRACT_VERSION
OPENAPI_FILE = "openapi.json"
MANIFEST_FILE = "manifest.json"
EXPORT_COMMAND = "agentrouter contract export"

# Severities, most severe first. `breaking` fails CI.
BREAKING = "breaking"
RISKY = "risky"
ADDITIVE = "additive"
SEVERITY_ORDER = (BREAKING, RISKY, ADDITIVE)

# Lists whose order carries no meaning — sorted so the artifact is stable.
_ORDER_INSENSITIVE = frozenset({"required", "enum", "tags"})


class ContractError(Exception):
    """Raised when a contract cannot be produced, read or compared."""


class ServerExtraMissing(ContractError):
    """The optional ``[server]`` extra is not installed, so there is no API to describe.

    Distinct from a missing or untrustworthy baseline: nothing is wrong with the
    contract, the tool simply cannot render one here. Callers must not tell the
    user to run `contract export` — that would fail identically.
    """


# --------------------------------------------------------------------------- #
# canonicalisation
# --------------------------------------------------------------------------- #


def _canonical(value: Any, key: str | None = None) -> Any:
    """Recursively sort mappings and order-insensitive lists."""
    if isinstance(value, dict):
        return {k: _canonical(value[k], k) for k in sorted(value)}
    if isinstance(value, list):
        items = [_canonical(v) for v in value]
        if key in _ORDER_INSENSITIVE and all(isinstance(i, str) for i in items):
            return sorted(items)
        if key == "parameters":
            # parameter order is not semantic; sort by (in, name) for stability
            return sorted(
                items,
                key=lambda p: (
                    (str(p.get("in", "")), str(p.get("name", "")))
                    if isinstance(p, dict)
                    else ("", "")
                ),
            )
        return items
    return value


def canonical_openapi(app: Any | None = None) -> dict:
    """Deterministic OpenAPI document rendered from the real FastAPI app.

    Environment-dependent fields (``servers``, which reflects whatever base URL
    the process was started with) are dropped so the artifact does not depend on
    how the exporting machine happened to run the app.
    """
    if app is None:
        try:
            from .server.app import create_app
        except ImportError as e:  # the REST surface is an optional extra
            raise ServerExtraMissing(
                "the HTTP contract needs the optional server extra; "
                "install it with: pip install 'agentrouter-os[server]'"
            ) from e

        app = create_app()
    try:
        doc = app.openapi()
    except Exception as e:  # pragma: no cover - defensive
        raise ContractError(f"could not render the OpenAPI document: {e}") from e
    doc = json.loads(json.dumps(doc))  # detach from FastAPI's cached object
    # Only the trivial default is environment noise. A real `servers` entry means
    # the app is mounted under a root_path, which moves every URL — that must stay
    # visible to the checker rather than being normalised away.
    if doc.get("servers") in ([], [{"url": "/"}], None):
        doc.pop("servers", None)
    return _canonical(doc)


def dumps(doc: dict) -> str:
    """Canonical JSON text (stable key order, trailing newline)."""
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _source_commit() -> str:
    try:
        proc = subprocess.run(  # nosec B603 B607 - fixed argv, read-only provenance
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _tool_version() -> str:
    try:
        from importlib.metadata import version

        return f"fastapi {version('fastapi')}"
    except Exception:
        return "fastapi unknown"


def build_manifest(doc: dict, *, generated_at: str | None = None) -> dict:
    """Provenance for an exported contract (never part of the comparison)."""
    return {
        "product_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "openapi_version": doc.get("openapi", "unknown"),
        "api_title": doc.get("info", {}).get("title", "unknown"),
        "api_version": doc.get("info", {}).get("version", "unknown"),
        "generation_command": EXPORT_COMMAND,
        "generation_tool": _tool_version(),
        "source_commit": _source_commit(),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "operation_count": sum(
            1
            for methods in doc.get("paths", {}).values()
            for m in methods
            if m in ("get", "put", "post", "delete", "patch", "head", "options", "trace")
        ),
    }


def contract_paths(root: Path) -> tuple[Path, Path]:
    base = root / CONTRACT_DIR
    return base / OPENAPI_FILE, base / MANIFEST_FILE


def _safe_write(path: Path, text: str, *, root: Path) -> None:
    """Write a contract artifact without following a symlink or escaping ``root``.

    Both filenames are fixed, so the risk is not arbitrary content anywhere — it
    is clobbering: a symlink planted at the target would redirect the write onto
    an unrelated file, and an unnormalised root can point outside the project.
    """
    resolved_root = root.resolve()
    try:
        path.resolve().relative_to(resolved_root)
    except ValueError as e:
        raise ContractError(f"refusing to write outside {resolved_root}: {path}") from e
    if path.is_symlink():
        raise ContractError(f"refusing to write through a symlink: {path}; remove it and re-run")
    path.write_text(text, encoding="utf-8")


def export_contract(root: Path, *, app: Any | None = None) -> tuple[Path, dict]:
    """Write the canonical contract + manifest under ``root``. Returns (path, doc)."""
    doc = canonical_openapi(app)
    openapi_path, manifest_path = contract_paths(root)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    _safe_write(openapi_path, dumps(doc), root=root)
    _safe_write(manifest_path, dumps(build_manifest(doc)), root=root)
    return openapi_path, doc


def load_baseline(root: Path) -> dict:
    """Read the committed contract. A missing baseline is an error, never a pass."""
    openapi_path, _ = contract_paths(root)
    if not openapi_path.exists():
        raise ContractError(
            f"no committed contract at {openapi_path}; run `{EXPORT_COMMAND}` and commit it"
        )
    try:
        data = json.loads(openapi_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ContractError(f"{openapi_path}: unreadable contract: {e}") from e
    if not isinstance(data, dict) or "paths" not in data:
        raise ContractError(f"{openapi_path}: not an OpenAPI document (no 'paths')")
    broken = validate_refs(data)
    if broken:
        # Refuse rather than compare: a dangling ref inlines as an empty schema,
        # which would make the baseline look permissive and hide real breaks.
        raise ContractError(
            f"{openapi_path}: {len(broken)} unusable $ref(s) — the contract cannot be "
            f"trusted as a baseline: {', '.join(broken[:5])}"
        )
    return data


# --------------------------------------------------------------------------- #
# schema comparison
# --------------------------------------------------------------------------- #

_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


@dataclass(frozen=True)
class Change:
    severity: str
    kind: str
    location: str
    detail: str

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "kind": self.kind,
            "location": self.location,
            "detail": self.detail,
        }


@dataclass
class Report:
    changes: list[Change] = field(default_factory=list)

    def add(self, severity: str, kind: str, location: str, detail: str) -> None:
        self.changes.append(Change(severity, kind, location, detail))

    @property
    def breaking(self) -> list[Change]:
        return [c for c in self.changes if c.severity == BREAKING]

    @property
    def risky(self) -> list[Change]:
        return [c for c in self.changes if c.severity == RISKY]

    @property
    def additive(self) -> list[Change]:
        return [c for c in self.changes if c.severity == ADDITIVE]

    @property
    def compatible(self) -> bool:
        return not self.breaking

    def as_dict(self) -> dict:
        return {
            "compatible": self.compatible,
            "counts": {
                BREAKING: len(self.breaking),
                RISKY: len(self.risky),
                ADDITIVE: len(self.additive),
            },
            "changes": [
                c.as_dict()
                for c in sorted(
                    self.changes,
                    key=lambda c: (SEVERITY_ORDER.index(c.severity), c.location, c.kind),
                )
            ],
        }


# Inlining a $ref graph re-expands shared nodes, so a small but deeply branching
# document can blow up exponentially. The gate reads a file from the repository,
# which a pull request can edit, so the expansion is bounded rather than trusted.
_MAX_EXPANDED_NODES = 200_000
_MAX_REF_DEPTH = 64


def validate_refs(doc: dict) -> list[str]:
    """Return every ``$ref`` in ``doc`` that does not resolve to a real component.

    An unresolvable or self-referential ref used to silently inline as ``{}``,
    which made the schema look empty and *hid* real breaking changes — a
    one-line edit to the committed baseline could turn the gate green. Callers
    reject such a document instead of comparing it.
    """
    bad: list[str] = []
    # `visiting` is the current DFS stack, so a ref that reaches itself is a
    # cycle; `validated` memoises refs already cleared. Without the memo a
    # document whose components each reference the previous one twice takes
    # exponential time to validate — the check meant to protect CI would hang
    # it. A ref in `validated` has, by definition, finished and left the stack,
    # so skipping it cannot mask a cycle.
    visiting: set[str] = set()
    validated: set[str] = set()
    budget = [_MAX_EXPANDED_NODES]

    def walk(node: Any) -> None:
        budget[0] -= 1
        if budget[0] <= 0:
            raise ContractError(
                f"contract has more than {_MAX_EXPANDED_NODES} nodes; refusing to validate it"
            )
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        ref = node.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/"):
                bad.append(f"{ref} (only local refs are supported)")
                return
            if ref in visiting:
                bad.append(f"{ref} (self-referential)")
                return
            if ref in validated:
                return
            target: Any = doc
            for part in ref[2:].split("/"):
                if not isinstance(target, dict) or part not in target:
                    bad.append(f"{ref} (unresolvable)")
                    return
                target = target[part]
            visiting.add(ref)
            walk(target)
            visiting.discard(ref)
            validated.add(ref)
            return
        for value in node.values():
            walk(value)

    walk(doc)
    return sorted(set(bad))


def _resolve(
    schema: Any,
    doc: dict,
    seen: frozenset[str] = frozenset(),
    budget: list[int] | None = None,
    depth: int = 0,
) -> Any:
    """Inline ``$ref`` so schemas compare structurally, within a bounded budget."""
    if budget is None:
        budget = [_MAX_EXPANDED_NODES]
    budget[0] -= 1
    if budget[0] <= 0 or depth > _MAX_REF_DEPTH:
        raise ContractError(
            "contract is too large or too deeply nested to compare safely "
            f"(over {_MAX_EXPANDED_NODES} expanded nodes or {_MAX_REF_DEPTH} levels of $ref)"
        )
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        # validate_refs has already rejected refs that cannot resolve.
        if ref in seen or not ref.startswith("#/"):
            return {}
        target: Any = doc
        for part in ref[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                return {}
            target = target[part]
        return _resolve(target, doc, seen | {ref}, budget, depth + 1)
    return {k: _resolve(v, doc, seen, budget, depth + 1) for k, v in schema.items()}


def _type_of(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if isinstance(t, str):
        return t
    for combinator in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(combinator)
        if isinstance(variants, list):
            types = sorted({str(_type_of(v)) for v in variants if _type_of(v)})
            if types:
                return "|".join(types)
    return None


# Validation keywords whose *tightening* rejects payloads that used to be
# accepted. Direction differs per keyword, so each is paired with the comparison
# that means "stricter than before".
_UPPER_BOUNDS = ("maxLength", "maxItems", "maximum", "exclusiveMaximum", "maxProperties")
_LOWER_BOUNDS = ("minLength", "minItems", "minimum", "exclusiveMinimum", "minProperties")


def _compare_constraints(old: dict, new: dict, loc: str, report: Report, *, request: bool) -> None:
    """Detect validation-constraint changes that silently reject valid traffic.

    A narrowed ``maxLength`` or a new ``pattern`` breaks callers just as surely
    as a removed field, but leaves the type and property set untouched — so
    without this the checker reports no change at all.
    """
    for key in _UPPER_BOUNDS + _LOWER_BOUNDS:
        before, after = old.get(key), new.get(key)
        if before == after:
            continue
        # An absent bound is not "no information" — it is the unbounded end of
        # the range. Introducing maxLength where there was none rejects every
        # longer request that used to be valid, so it must compare as the
        # strongest tightening rather than as an unclassifiable change.
        upper = key in _UPPER_BOUNDS
        unbounded = float("inf") if upper else float("-inf")
        lhs = unbounded if before is None else before
        rhs = unbounded if after is None else after
        if not isinstance(lhs, (int, float)) or not isinstance(rhs, (int, float)):
            report.add(RISKY, "constraint_changed", loc, f"{key}: {before!r} -> {after!r}")
            continue
        tightened = rhs < lhs if upper else rhs > lhs
        severity = (BREAKING if tightened else ADDITIVE) if request else RISKY
        kind = "constraint_tightened" if tightened else "constraint_relaxed"
        report.add(severity, kind, loc, f"{key}: {before} -> {after}")

    if old.get("pattern") != new.get("pattern"):
        added_or_changed = new.get("pattern") is not None
        severity = (BREAKING if added_or_changed else ADDITIVE) if request else RISKY
        report.add(
            severity,
            "pattern_changed",
            loc,
            f"pattern: {old.get('pattern')!r} -> {new.get('pattern')!r}",
        )

    old_extra, new_extra = old.get("additionalProperties"), new.get("additionalProperties")
    if old_extra != new_extra:
        closed = new_extra is False and old_extra is not False
        severity = (BREAKING if closed else ADDITIVE) if request else RISKY
        report.add(
            severity,
            "additional_properties_closed" if closed else "additional_properties_changed",
            loc,
            f"additionalProperties: {old_extra!r} -> {new_extra!r}",
        )


def _compare_schema(
    old: Any, new: Any, doc_old: dict, doc_new: dict, loc: str, report: Report, *, request: bool
) -> None:
    old = _resolve(old, doc_old)
    new = _resolve(new, doc_new)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return

    old_t, new_t = _type_of(old), _type_of(new)
    if old_t and new_t and old_t != new_t:
        report.add(
            BREAKING,
            "request_type_changed" if request else "response_type_changed",
            loc,
            f"type {old_t} -> {new_t}",
        )

    old_enum, new_enum = old.get("enum"), new.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        removed = [v for v in old_enum if v not in new_enum]
        added = [v for v in new_enum if v not in old_enum]
        if removed:
            report.add(
                BREAKING, "enum_narrowed", loc, f"values removed: {sorted(map(str, removed))}"
            )
        if added:
            report.add(RISKY, "enum_expanded", loc, f"values added: {sorted(map(str, added))}")

    if old.get("format") != new.get("format"):
        report.add(RISKY, "format_changed", loc, f"{old.get('format')} -> {new.get('format')}")
    if old.get("default") != new.get("default"):
        report.add(
            RISKY, "default_changed", loc, f"{old.get('default')!r} -> {new.get('default')!r}"
        )
    _compare_constraints(old, new, loc, report, request=request)

    old_props = old.get("properties") if isinstance(old.get("properties"), dict) else {}
    new_props = new.get("properties") if isinstance(new.get("properties"), dict) else {}
    old_req = set(old.get("required") or [])
    new_req = set(new.get("required") or [])

    for name in sorted(set(old_props) - set(new_props)):
        if request:
            severity, kind = (
                (BREAKING, "required_request_field_removed")
                if name in old_req
                else (RISKY, "request_field_removed")
            )
        else:
            severity, kind = BREAKING, "response_field_removed"
        report.add(severity, kind, f"{loc}.{name}", "field removed")

    for name in sorted(set(new_props) - set(old_props)):
        if name in new_req:
            report.add(
                BREAKING,
                "required_request_field_added" if request else "required_response_field_added",
                f"{loc}.{name}",
                "new field is required",
            )
        else:
            report.add(
                ADDITIVE,
                "optional_request_field_added" if request else "optional_response_field_added",
                f"{loc}.{name}",
                "new optional field",
            )

    for name in sorted(set(old_props) & set(new_props)):
        if name not in old_req and name in new_req:
            report.add(BREAKING, "field_became_required", f"{loc}.{name}", "optional -> required")
        elif name in old_req and name not in new_req:
            report.add(ADDITIVE, "field_became_optional", f"{loc}.{name}", "required -> optional")
        _compare_schema(
            old_props[name],
            new_props[name],
            doc_old,
            doc_new,
            f"{loc}.{name}",
            report,
            request=request,
        )

    if "items" in old or "items" in new:
        _compare_schema(
            old.get("items", {}),
            new.get("items", {}),
            doc_old,
            doc_new,
            f"{loc}[]",
            report,
            request=request,
        )


def _security_of(op: dict, doc: dict) -> list:
    sec = op.get("security")
    if sec is None:
        sec = doc.get("security", [])
    return sec if isinstance(sec, list) else []


def _content_schema(body: Any) -> Any:
    if not isinstance(body, dict):
        return {}
    content = body.get("content")
    if not isinstance(content, dict):
        return {}
    for media in ("application/json", *sorted(content)):
        if media in content and isinstance(content[media], dict):
            return content[media].get("schema", {})
    return {}


def _media_types(body: Any) -> set[str]:
    if not isinstance(body, dict):
        return set()
    content = body.get("content")
    return set(content) if isinstance(content, dict) else set()


def _compare_media_types(old: Any, new: Any, loc: str, report: Report) -> None:
    """A dropped media type makes the body unparseable even if the schema matches."""
    before, after = _media_types(old), _media_types(new)
    for media in sorted(before - after):
        report.add(BREAKING, "media_type_removed", loc, f"{media} no longer offered")
    for media in sorted(after - before):
        report.add(ADDITIVE, "media_type_added", loc, f"{media} now offered")


def _compare_parameters(
    old_op: dict, new_op: dict, doc_old: dict, doc_new: dict, loc: str, report: Report
) -> None:
    def index(op: dict) -> dict:
        out = {}
        for p in op.get("parameters", []) or []:
            if isinstance(p, dict) and "name" in p:
                out[(p.get("in"), p["name"])] = p
        return out

    old_p, new_p = index(old_op), index(new_op)
    for key in sorted(set(old_p) - set(new_p), key=str):
        report.add(BREAKING, "parameter_removed", f"{loc}.{key[1]}", f"{key[0]} parameter removed")
    for key in sorted(set(new_p) - set(old_p), key=str):
        severity = BREAKING if new_p[key].get("required") else ADDITIVE
        report.add(
            severity,
            "required_parameter_added"
            if new_p[key].get("required")
            else "optional_parameter_added",
            f"{loc}.{key[1]}",
            f"new {key[0]} parameter",
        )
    for key in sorted(set(old_p) & set(new_p), key=str):
        was, now = bool(old_p[key].get("required")), bool(new_p[key].get("required"))
        if not was and now:
            report.add(
                BREAKING, "parameter_became_required", f"{loc}.{key[1]}", "optional -> required"
            )
        elif was and not now:
            report.add(
                ADDITIVE, "parameter_became_optional", f"{loc}.{key[1]}", "required -> optional"
            )
        # A parameter's schema is where a type flip or a new `pattern` hides; a
        # name/required-only comparison would call that "no change".
        _compare_schema(
            old_p[key].get("schema", {}),
            new_p[key].get("schema", {}),
            doc_old,
            doc_new,
            f"{loc}.{key[1]}",
            report,
            request=True,
        )


def diff_contracts(old: dict, new: dict) -> Report:
    """Classify every difference between two OpenAPI documents."""
    report = Report()

    old_version = (old.get("info") or {}).get("version")
    new_version = (new.get("info") or {}).get("version")
    if old_version != new_version:
        report.add(RISKY, "api_version_changed", "info.version", f"{old_version} -> {new_version}")

    # `servers` is dropped at export only when it is the trivial default, so a
    # relocated app (root_path / mount prefix) shows up here instead of silently
    # changing every URL.
    if (old.get("servers") or []) != (new.get("servers") or []):
        report.add(
            BREAKING,
            "servers_changed",
            "servers",
            f"{old.get('servers')} -> {new.get('servers')} (every URL moves)",
        )

    old_paths = old.get("paths", {}) or {}
    new_paths = new.get("paths", {}) or {}

    for path in sorted(set(old_paths) - set(new_paths)):
        report.add(BREAKING, "endpoint_removed", path, "path no longer served")
    for path in sorted(set(new_paths) - set(old_paths)):
        report.add(ADDITIVE, "endpoint_added", path, "new path")

    for path in sorted(set(old_paths) & set(new_paths)):
        old_ops = old_paths[path] or {}
        new_ops = new_paths[path] or {}
        for method in sorted(set(old_ops) & set(_HTTP_METHODS) - set(new_ops)):
            report.add(BREAKING, "method_removed", f"{path}.{method}", "method no longer served")
        for method in sorted(set(new_ops) & set(_HTTP_METHODS) - set(old_ops)):
            report.add(ADDITIVE, "method_added", f"{path}.{method}", "new method")

        for method in sorted(set(old_ops) & set(new_ops) & set(_HTTP_METHODS)):
            loc = f"{path}.{method}"
            old_op, new_op = old_ops[method] or {}, new_ops[method] or {}

            if _security_of(old_op, old) != _security_of(new_op, new):
                report.add(
                    BREAKING,
                    "authentication_changed",
                    loc,
                    "security requirement changed",
                )

            if old_op.get("operationId") != new_op.get("operationId"):
                report.add(
                    RISKY,
                    "operation_id_changed",
                    loc,
                    f"{old_op.get('operationId')} -> {new_op.get('operationId')} "
                    "(renames the method in generated clients)",
                )
            if bool(old_op.get("deprecated")) != bool(new_op.get("deprecated")):
                report.add(
                    RISKY,
                    "deprecation_changed",
                    loc,
                    f"deprecated: {bool(old_op.get('deprecated'))} -> "
                    f"{bool(new_op.get('deprecated'))}",
                )

            _compare_parameters(old_op, new_op, old, new, f"{loc}.parameters", report)
            _compare_media_types(
                old_op.get("requestBody"), new_op.get("requestBody"), f"{loc}.request", report
            )
            _compare_schema(
                _content_schema(old_op.get("requestBody")),
                _content_schema(new_op.get("requestBody")),
                old,
                new,
                f"{loc}.request",
                report,
                request=True,
            )

            old_resp = old_op.get("responses", {}) or {}
            new_resp = new_op.get("responses", {}) or {}
            for status in sorted(set(old_resp) - set(new_resp)):
                report.add(
                    BREAKING,
                    "response_status_removed",
                    f"{loc}.{status}",
                    "status no longer documented",
                )
            for status in sorted(set(new_resp) - set(old_resp)):
                report.add(
                    ADDITIVE, "response_status_added", f"{loc}.{status}", "newly documented status"
                )
            for status in sorted(set(old_resp) & set(new_resp)):
                _compare_media_types(old_resp[status], new_resp[status], f"{loc}.{status}", report)
                _compare_schema(
                    _content_schema(old_resp[status]),
                    _content_schema(new_resp[status]),
                    old,
                    new,
                    f"{loc}.{status}",
                    report,
                    request=False,
                )

            if (old_op.get("description") or "") != (new_op.get("description") or "") or (
                old_op.get("summary") or ""
            ) != (new_op.get("summary") or ""):
                report.add(
                    RISKY, "documented_semantics_changed", loc, "summary/description changed"
                )

    return report


def check(root: Path, *, app: Any | None = None) -> tuple[Report, dict]:
    """Compare the live app against the committed baseline. Never regenerates it."""
    baseline = load_baseline(root)
    current = canonical_openapi(app)
    return diff_contracts(baseline, current), current
