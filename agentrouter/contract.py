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

import contextlib
import json
import os
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
# A break the owner reviewed and recorded in the manifest. Still a break, still
# reported loudly — but it must not block forever, or the documented acceptance
# workflow is a dead end (see `Report.apply_acceptances`).
ACCEPTED = "accepted"
SEVERITY_ORDER = (BREAKING, ACCEPTED, RISKY, ADDITIVE)

# Lists whose order carries no meaning — sorted so the artifact is stable.
_ORDER_INSENSITIVE = frozenset({"required", "enum", "tags"})


class ContractError(Exception):
    """Raised when a contract cannot be produced, read or compared."""


class BaselineMissing(ContractError):
    """No contract has been committed yet — genuinely nothing to protect.

    Distinct from a baseline that exists but cannot be read. Collapsing the two
    is a gate bypass: `contract export` may proceed silently on the first export,
    so treating an *unparseable* baseline as "missing" lets anyone erase the
    breaking-change refusal by corrupting the file instead of deleting it.
    """


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
        if key in ("anyOf", "oneOf", "allOf"):
            # Branch order carries no meaning. Without this a library upgrade
            # that reorders union members produces a positional mismatch and
            # reports a breaking type change on a byte-equivalent API.
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
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


def _source_commit(root: Path | None = None) -> str:
    """HEAD of the tree being exported (not the caller's cwd, which may be elsewhere)."""
    try:
        proc = subprocess.run(  # nosec B603 B607 - fixed argv, read-only provenance
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(root) if root else None,
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


def build_manifest(doc: dict, *, generated_at: str | None = None, root: Path | None = None) -> dict:
    """Provenance for an exported contract (never part of the comparison)."""
    return {
        "product_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "openapi_version": doc.get("openapi", "unknown"),
        "api_title": doc.get("info", {}).get("title", "unknown"),
        "api_version": doc.get("info", {}).get("version", "unknown"),
        "generation_command": EXPORT_COMMAND,
        "generation_tool": _tool_version(),
        "source_commit": _source_commit(root),
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
    # O_NOFOLLOW closes the gap between the checks above and the write, and a
    # link count above one means the inode is shared — a hardlink is invisible to
    # is_symlink() and resolves inside the root, so without this a planted
    # hardlink would still redirect the write onto the file it shares.
    # Deliberately no O_TRUNC: truncation would empty the victim before the link
    # count below could refuse the write. Truncate only once the inode is known
    # to be ours alone.
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except OSError as e:
        raise ContractError(f"refusing to write {path}: {e}") from e
    try:
        if os.fstat(fd).st_nlink > 1:
            raise ContractError(
                f"refusing to write through a hardlink: {path}; remove it and re-run"
            )
        os.ftruncate(fd, 0)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as fh:
            fh.write(text)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise


def export_contract(root: Path, *, app: Any | None = None) -> tuple[Path, dict]:
    """Write the canonical contract + manifest under ``root``. Returns (path, doc)."""
    doc = canonical_openapi(app)
    openapi_path, manifest_path = contract_paths(root)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    _safe_write(openapi_path, dumps(doc), root=root)
    _safe_write(manifest_path, dumps(build_manifest(doc, root=root)), root=root)
    return openapi_path, doc


def load_baseline_file(openapi_path: Path) -> dict:
    """Read and sanity-check one contract file. A missing file is an error, never a pass."""
    if not openapi_path.exists():
        raise BaselineMissing(
            f"no committed contract at {openapi_path}; run `{EXPORT_COMMAND}` and commit it"
        )
    try:
        data = json.loads(openapi_path.read_text(encoding="utf-8"))
    except RecursionError as e:
        # A deeply nested document blows the stack inside json.loads itself.
        raise ContractError(f"{openapi_path}: nested too deeply to parse safely") from e
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


def load_baseline(root: Path) -> dict:
    """Read the committed contract under ``root``."""
    openapi_path, _ = contract_paths(root)
    return load_baseline_file(openapi_path)


# --------------------------------------------------------------------------- #
# schema comparison
# --------------------------------------------------------------------------- #

# Inlining a $ref graph re-expands shared nodes, so a small but deeply branching
# document can blow up exponentially. The gate reads a file from the repository,
# which a pull request can edit, so the expansion is bounded rather than trusted.
_MAX_EXPANDED_NODES = 200_000
_MAX_REF_DEPTH = 64
# `_compare_schema` recurses through nested properties independently of $ref, so
# it needs its own ceiling well under the interpreter's recursion limit.
_MAX_COMPARE_DEPTH = 128

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

    # One expansion budget for the WHOLE comparison, not per call.
    #
    # `_resolve` used to allocate a fresh budget on every entry, and
    # `_compare_schema` re-enters it for every property, parameter, media type
    # and status — so the advertised "at most N expanded nodes" was really N per
    # comparison root, and total work grew linearly with the number of shared
    # operations. Measured on crafted fan-out documents that was 73s from an
    # 11 KB file, scaling cleanly with path count. Sharing one counter makes the
    # bound mean what the error message says it means.
    budget: list[int] = field(default_factory=lambda: [_MAX_EXPANDED_NODES])
    # Guards `_compare_schema`'s own recursion, which is separate from `$ref`
    # depth: a schema nested 20k levels deep contains no refs at all but still
    # overflows the interpreter stack.
    depth: int = 0

    def add(self, severity: str, kind: str, location: str, detail: str) -> None:
        self.changes.append(Change(severity, kind, location, detail))

    def spend(self, n: int = 1) -> None:
        """Charge the shared budget; raise once the whole comparison is too big."""
        self.budget[0] -= n
        if self.budget[0] <= 0:
            raise ContractError(
                f"contract is too large to compare safely (over {_MAX_EXPANDED_NODES} "
                "expanded nodes across the whole document)"
            )

    @contextlib.contextmanager
    def descend(self) -> Any:
        if self.depth >= _MAX_COMPARE_DEPTH:
            raise ContractError(
                f"contract is nested too deeply to compare safely "
                f"(over {_MAX_COMPARE_DEPTH} levels)"
            )
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def apply_acceptances(self, recorded: set[tuple[str, str]]) -> None:
        """Downgrade breaks the owner has explicitly reviewed and recorded.

        Without this the acceptance workflow cannot complete. `contract export
        --accept-breaking` moves the branch baseline, so the in-branch check goes
        green — but CI also compares against the BASE branch, which still holds
        the old contract and reports the same break. The result was a change that
        could be accepted and could never merge.

        Matching is on (kind, location), i.e. the checker's own findings, so an
        acceptance can only excuse the exact break that was recorded. A new,
        different break in the same PR is still breaking.
        """
        if not recorded:
            return
        self.changes = [
            Change(ACCEPTED, c.kind, c.location, f"{c.detail} [owner-accepted]")
            if c.severity == BREAKING and (c.kind, c.location) in recorded
            else c
            for c in self.changes
        ]

    @property
    def breaking(self) -> list[Change]:
        return [c for c in self.changes if c.severity == BREAKING]

    @property
    def accepted(self) -> list[Change]:
        return [c for c in self.changes if c.severity == ACCEPTED]

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
                ACCEPTED: len(self.accepted),
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
    """Inline ``$ref`` so schemas compare structurally, within a bounded budget.

    ``budget`` is a single mutable counter shared across an entire comparison —
    callers inside ``diff_contracts`` pass ``report.budget``. Allocating a fresh
    one per call (the old default) meant the ceiling applied per schema rather
    than per run, so total work still grew without bound as the API grew.
    """
    if budget is None:
        budget = [_MAX_EXPANDED_NODES]
    budget[0] -= 1
    if budget[0] <= 0 or depth > _MAX_REF_DEPTH:
        raise ContractError(
            "contract is too large or nested too deeply to compare safely "
            f"(over {_MAX_EXPANDED_NODES} expanded nodes, or {_MAX_REF_DEPTH} levels of "
            "nesting — `$ref` hops and plain object nesting both count)"
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


_COMBINATORS = ("anyOf", "oneOf", "allOf")


def _type_of(schema: Any) -> str | None:
    """Normalised type name, or None when the schema states no type at all.

    Handles OpenAPI 3.1's list form (``type: ["integer", "null"]``) as well as
    the string form. The document declares 3.1, so the list form is legal — and
    since the baseline is a hand-editable committed file, not reading it would be
    a one-edit way to switch off type checking on any field.
    """
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        names = sorted({x for x in t if isinstance(x, str)})
        if names:
            return "|".join(names)
    for combinator in _COMBINATORS:
        variants = schema.get(combinator)
        if isinstance(variants, list):
            types = sorted({str(_type_of(v)) for v in variants if _type_of(v)})
            if types:
                return "|".join(types)
    return None


def _is_null_variant(schema: Any) -> bool:
    """True for the ``{"type": "null"}`` branch, in either 3.1 spelling."""
    if not isinstance(schema, dict):
        return False
    t = schema.get("type")
    return t == "null" or (isinstance(t, list) and set(t) == {"null"})


def _nullable(schema: Any) -> bool:
    """Whether ``null`` is an accepted value, however it is spelled."""
    if not isinstance(schema, dict):
        return False
    t = schema.get("type")
    if t == "null" or (isinstance(t, list) and "null" in t):
        return True
    for combinator in ("anyOf", "oneOf"):
        variants = schema.get(combinator)
        if isinstance(variants, list) and any(_nullable(v) for v in variants):
            return True
    return False


def _enum_values(schema: Any) -> list | None:
    """Accepted values for a schema, or None when it is unconstrained.

    ``const`` is a one-element enum and pydantic emits it for ``Literal[...]``,
    so it must be read here or a `Literal` field's value could be changed with
    the gate green.
    """
    if not isinstance(schema, dict):
        return None
    values = schema.get("enum")
    if isinstance(values, list):
        return values
    if "const" in schema:
        return [schema["const"]]
    return None


def _is_untyped(schema: Any) -> bool:
    """A schema that constrains nothing — what `Any` renders as.

    Going from a typed field to this is a withdrawn guarantee on a response and
    a widening on a request, but `_type_of` returns None for it, so a plain
    ``old_t and new_t`` comparison silently skips the change entirely.
    """
    if not isinstance(schema, dict):
        return False
    meaningful = set(schema) - {"title", "description", "default", "example", "examples"}
    return not meaningful


def _unwrap(schema: Any) -> tuple[Any, bool, list, str]:
    """Split a schema into (payload, nullable, remaining variants).

    FastAPI renders every ``T | None`` field as ``anyOf: [T, {"type": "null"}]``,
    which is *most* fields on this API. Comparing only the top level of such a
    node means a narrowed enum, a tightened constraint or a changed item type
    inside ``T`` is invisible — so the fields the response models declare would
    be protected for presence only. Unwrap the null variant and hand back the
    single meaningful schema so the caller can recurse into it.

    Returns ``(payload, nullable, remaining_branches, combinator)``. The
    combinator name matters: ``anyOf``/``oneOf`` are alternatives, so more
    branches is *more* permissive, while ``allOf`` is a conjunction, so more
    branches is *less* permissive. Treating them alike inverted the
    classification for every ``allOf``.
    """
    if not isinstance(schema, dict):
        return schema, False, [], "anyOf"
    for combinator in _COMBINATORS:
        variants = schema.get(combinator)
        if not isinstance(variants, list) or not variants:
            continue
        nullable = _nullable(schema)
        rest = [v for v in variants if not _is_null_variant(v)]
        if len(rest) == 1:
            # Merge sibling keywords (title/default/format live outside the
            # combinator) so constraint comparison still sees them.
            inner = dict(rest[0]) if isinstance(rest[0], dict) else rest[0]
            if isinstance(inner, dict):
                for key, value in schema.items():
                    if key not in _COMBINATORS and key not in inner:
                        inner[key] = value
            return inner, nullable, [], combinator
        return schema, nullable, rest, combinator
    return schema, _nullable(schema), [], "anyOf"


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
        # `False` closes the object outright; a *schema* constrains what the extra
        # properties may be, which rejects previously-valid payloads just as
        # surely. Reading only the `False` case classified that as additive.
        closed = (new_extra is False and old_extra is not False) or (
            isinstance(new_extra, dict) and old_extra is not False and new_extra != old_extra
        )
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
    """Depth-guarded entry point. Every recursion goes through here, so one
    wrapper bounds the whole traversal instead of each call site guarding itself."""
    with report.descend():
        _compare_schema_inner(old, new, doc_old, doc_new, loc, report, request=request)


def _compare_schema_inner(
    old: Any, new: Any, doc_old: dict, doc_new: dict, loc: str, report: Report, *, request: bool
) -> None:
    report.spend()
    old = _resolve(old, doc_old, budget=report.budget)
    new = _resolve(new, doc_new, budget=report.budget)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return

    old_t, new_t = _type_of(old), _type_of(new)

    # Peel the `anyOf[T, null]` wrapper before anything else, so the comparison
    # below applies to T rather than to the union node. Nullability itself is
    # reported separately because its direction matters.
    old_inner, old_null, old_rest, old_comb = _unwrap(old)
    new_inner, new_null, new_rest, new_comb = _unwrap(new)
    if old_null != new_null:
        # A request that starts accepting null is more permissive; a response
        # that starts *returning* null breaks a caller that never checked.
        widened = new_null
        severity = (
            (ADDITIVE if widened else BREAKING) if request else (BREAKING if widened else ADDITIVE)
        )
        report.add(
            severity,
            "became_nullable" if widened else "became_non_nullable",
            loc,
            f"nullable: {old_null} -> {new_null}",
        )

    # Type erasure is a change even though `_type_of` reports None for it: a
    # response that stops declaring its type withdraws a guarantee, and a request
    # that does the same accepts more. Handled before the union logic because an
    # erased schema has no branches left to compare.
    old_bare, new_bare = _is_untyped(old), _is_untyped(new)
    if old_bare != new_bare:
        erased = new_bare
        severity = (ADDITIVE if erased else BREAKING) if request else RISKY
        report.add(
            severity,
            "type_erased" if erased else "type_declared",
            loc,
            "schema no longer constrains the value"
            if erased
            else "schema now constrains a previously free value",
        )
        return

    if (old_rest or new_rest) and len(old_rest) == len(new_rest) and old_comb == new_comb:
        # Same shape of union on both sides: compare branch by branch. Branch
        # order is not semantic, so `_canonical` sorts these lists — otherwise a
        # library upgrade that reorders union members turns CI red on a
        # byte-equivalent API.
        for i, (o, n) in enumerate(zip(old_rest, new_rest, strict=True)):
            _compare_schema(o, n, doc_old, doc_new, f"{loc}|{i}", report, request=request)
    elif old_rest or new_rest or old_comb != new_comb:
        # Arity or combinator changed. `anyOf`/`oneOf` are alternatives, so more
        # branches is MORE permissive; `allOf` is a conjunction, so more branches
        # is LESS permissive. Counting them alike classified every `allOf`
        # backwards. Count the real branch totals, including the single-branch
        # case that `_unwrap` already collapsed, so the reported numbers are not
        # "0 -> 2" for a 1 -> 2 change.
        before = len(old_rest) or (1 if isinstance(old_inner, dict) else 0)
        after = len(new_rest) or (1 if isinstance(new_inner, dict) else 0)
        conjunction = "allOf" in (old_comb, new_comb)
        stricter = (before < after) if conjunction else (after < before)
        severity = (BREAKING if stricter else ADDITIVE) if request else RISKY
        report.add(
            severity,
            "union_narrowed" if stricter else "union_widened",
            loc,
            f"{old_comb}[{before}] -> {new_comb}[{after}]",
        )
        return
    elif old_inner is not old or new_inner is not new:
        # Recurse into the unwrapped payload; the union node itself carries no
        # further information once nullability has been reported.
        _compare_schema(old_inner, new_inner, doc_old, doc_new, loc, report, request=request)
        return

    if old_t and new_t and old_t != new_t:
        report.add(
            BREAKING,
            "request_type_changed" if request else "response_type_changed",
            loc,
            f"type {old_t} -> {new_t}",
        )

    # `enum` and `const` are the same constraint at different cardinalities, and
    # both must be compared even when only ONE side has them: introducing an enum
    # on a previously free-form request field is the most extreme narrowing there
    # is (every value but the listed ones starts returning 422), and it used to
    # report nothing at all because the comparison required two lists.
    old_enum = _enum_values(old)
    new_enum = _enum_values(new)
    if old_enum is not None or new_enum is not None:
        if old_enum is None:
            # unconstrained -> constrained
            severity = BREAKING if request else RISKY
            report.add(severity, "enum_introduced", loc, f"now limited to {sorted(new_enum or [])}")
        elif new_enum is None:
            # constrained -> unconstrained: a request accepts more; a response
            # may now return values the client never expected.
            severity = ADDITIVE if request else RISKY
            report.add(severity, "enum_removed", loc, "no longer limited to a fixed set")
        else:
            removed = [v for v in old_enum if v not in new_enum]
            added = [v for v in new_enum if v not in old_enum]
            if removed:
                # Fewer accepted values breaks a REQUEST caller. On a response,
                # promising fewer values is safe — it is expansion that surprises
                # a client switching on the value.
                severity = BREAKING if request else ADDITIVE
                report.add(
                    severity, "enum_narrowed", loc, f"values removed: {sorted(map(str, removed))}"
                )
            if added:
                severity = ADDITIVE if request else RISKY
                report.add(
                    severity, "enum_expanded", loc, f"values added: {sorted(map(str, added))}"
                )

    if old.get("format") != new.get("format"):
        # pydantic enforces `format` on input (uuid, date-time, ...), so adding
        # one to a request rejects values that used to be accepted — the same
        # break `pattern` gets, and it was inconsistent to treat them differently.
        tightened = new.get("format") is not None
        severity = (BREAKING if tightened else ADDITIVE) if request else RISKY
        report.add(severity, "format_changed", loc, f"{old.get('format')} -> {new.get('format')}")
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
        if name in new_req and request:
            # Only a *request* field can break a caller by becoming mandatory:
            # the caller has to start sending it. A new required RESPONSE field
            # is strictly more data arriving, which no client breaks on — and
            # FastAPI marks every non-defaulted response field required, so
            # calling it breaking would fail CI on the single most common
            # additive change there is, and train maintainers to reach for
            # --accept-breaking. That is how a gate dies.
            report.add(
                BREAKING,
                "required_request_field_added",
                f"{loc}.{name}",
                "new field is required",
            )
        else:
            report.add(
                ADDITIVE,
                "optional_request_field_added" if request else "response_field_added",
                f"{loc}.{name}",
                "new optional field" if request else "new response field",
            )

    for name in sorted(set(old_props) & set(new_props)):
        # `required` means the opposite thing in each direction. On a request it
        # is an obligation on the caller, so making it required breaks them. On
        # a response it is a guarantee from the server, so making it required is
        # a stronger promise (additive) and dropping it withdraws one (breaking).
        if name not in old_req and name in new_req:
            severity = BREAKING if request else ADDITIVE
            report.add(severity, "field_became_required", f"{loc}.{name}", "optional -> required")
        elif name in old_req and name not in new_req:
            severity = ADDITIVE if request else BREAKING
            report.add(severity, "field_became_optional", f"{loc}.{name}", "required -> optional")
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


def _security_key(requirement: Any) -> str:
    """Stable identity for one alternative in a security requirement list."""
    if not isinstance(requirement, dict):
        return str(requirement)
    return json.dumps(requirement, sort_keys=True)


def _compare_security(old_op: dict, new_op: dict, old: dict, new: dict, loc: str, report: Report):
    """The entries of `security` are alternatives (OR), so compare them as a set.

    Adding a second accepted scheme is additive — every existing caller still
    authenticates. Removing an alternative breaks the callers using it. The old
    equality check reported both as one undifferentiated breaking change.
    """
    before = {_security_key(r) for r in _security_of(old_op, old)}
    after = {_security_key(r) for r in _security_of(new_op, new)}
    if before == after:
        return
    removed, added = before - after, after - before
    if removed:
        # Dropping the last alternative means the endpoint is now unauthenticated,
        # which is a security regression rather than a client break — but it is
        # the more urgent of the two, so it keeps the breaking severity.
        detail = (
            "endpoint no longer requires authentication" if not after else "alternative removed"
        )
        report.add(
            BREAKING,
            "authentication_removed" if not after else "authentication_changed",
            loc,
            detail,
        )
    if added and not removed:
        severity = BREAKING if not before else ADDITIVE
        report.add(
            severity,
            "authentication_added" if not before else "authentication_alternative_added",
            loc,
            "endpoint now requires authentication"
            if not before
            else "an additional accepted scheme",
        )


def _compare_security_schemes(old: dict, new: dict, report: Report) -> None:
    """Compare the scheme DEFINITIONS, not just which scheme an operation names.

    An operation keeps requiring `APIKeyHeader` while the scheme itself is
    redefined from `X-API-Key` to `Authorization`, or from an apiKey header to a
    cookie. The requirement is unchanged, so comparing only the requirement (as
    `_compare_security` does) reports nothing while every existing client stops
    authenticating.
    """
    old_s = (old.get("components") or {}).get("securitySchemes") or {}
    new_s = (new.get("components") or {}).get("securitySchemes") or {}
    if not isinstance(old_s, dict) or not isinstance(new_s, dict):
        return
    for name in sorted(set(old_s) - set(new_s)):
        report.add(BREAKING, "security_scheme_removed", f"securitySchemes.{name}", "scheme removed")
    for name in sorted(set(new_s) - set(old_s)):
        report.add(ADDITIVE, "security_scheme_added", f"securitySchemes.{name}", "scheme added")
    for name in sorted(set(old_s) & set(new_s)):
        before, after = old_s[name], new_s[name]
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue
        # `name`/`in` are where the credential is carried; `type`/`scheme` are how
        # it is formed. Changing any of them invalidates every existing caller.
        # `flows` is where an oauth2 scheme's authorization and token endpoints
        # live — repointing them changes where the credential comes from, which
        # is the most consequential change a scheme can undergo.
        for attr in ("type", "name", "in", "scheme", "bearerFormat", "openIdConnectUrl", "flows"):
            if before.get(attr) != after.get(attr):
                report.add(
                    BREAKING,
                    "security_scheme_changed",
                    f"securitySchemes.{name}.{attr}",
                    f"{before.get(attr)!r} -> {after.get(attr)!r}",
                )


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


def _status_still_covered(status: str, present: set[str]) -> bool:
    """Whether a removed status is still described by what remains.

    OpenAPI allows both a wildcard class (`4XX`) and explicit codes (`404`).
    Swapping one spelling for the other changes no behaviour, so it must not be
    reported as a removed response.
    """
    status = str(status)
    if status.upper().endswith("XX") and len(status) == 3:
        prefix = status[0]
        return any(c.startswith(prefix) and c[1:].isdigit() for c in map(str, present))
    if status.isdigit() and len(status) == 3:
        return f"{status[0]}XX" in present or f"{status[0]}xx" in present
    return False


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

    _compare_security_schemes(old, new, report)

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

            _compare_security(old_op, new_op, old, new, loc, report)

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

            old_body = old_op.get("requestBody") or {}
            new_body = new_op.get("requestBody") or {}
            old_body_req = bool(isinstance(old_body, dict) and old_body.get("required"))
            new_body_req = bool(isinstance(new_body, dict) and new_body.get("required"))
            if old_body_req != new_body_req:
                # An optional body becoming mandatory breaks every caller that
                # sent none. Only `content` was being read, so this was invisible.
                report.add(
                    BREAKING if new_body_req else ADDITIVE,
                    "request_body_became_required"
                    if new_body_req
                    else "request_body_became_optional",
                    f"{loc}.request",
                    f"required: {old_body_req} -> {new_body_req}",
                )

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
                # `4XX` replaced by explicit `401/404/422` documents MORE, not
                # less: the same responses are still described, just precisely.
                # Flagging that as a removal made a documentation improvement
                # fail CI. Only a class that is genuinely no longer covered is
                # a removal.
                if _status_still_covered(status, set(new_resp)):
                    report.add(
                        RISKY,
                        "response_status_refined",
                        f"{loc}.{status}",
                        "replaced by explicit codes in the same class",
                    )
                    continue
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


def recorded_acceptances(root: Path) -> set[tuple[str, str]]:
    """(kind, location) pairs the owner has explicitly reviewed and recorded.

    Read from the manifest in the tree being checked, so the acceptance travels
    with the change and is visible in the pull-request diff. A missing or
    unreadable manifest simply yields nothing — an acceptance must be present and
    parseable to excuse anything.
    """
    _, manifest_path = contract_paths(root)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return set()
    pairs: set[tuple[str, str]] = set()
    for entry in manifest.get("accepted_breaking_changes") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if isinstance(change, dict) and change.get("kind") and change.get("location"):
                pairs.add((str(change["kind"]), str(change["location"])))
    return pairs


def check(
    root: Path, *, app: Any | None = None, baseline_path: Path | None = None
) -> tuple[Report, dict]:
    """Compare the live app against the committed baseline. Never regenerates it.

    Renders the live document FIRST so a core-only install fails with
    ``ServerExtraMissing`` rather than with "no committed contract" — otherwise
    the user is told to run `contract export`, which cannot work there either.
    """
    current = canonical_openapi(app)
    baseline = load_baseline_file(baseline_path) if baseline_path else load_baseline(root)
    report = diff_contracts(baseline, current)
    # An owner-reviewed break recorded in THIS tree's manifest is reported but
    # does not block. Without this the acceptance workflow is a dead end: export
    # moves the branch baseline, but CI also compares against the base branch,
    # which still holds the old contract and reports the same break forever.
    report.apply_acceptances(recorded_acceptances(root))
    return report, current
