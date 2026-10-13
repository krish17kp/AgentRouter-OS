"""Versioned HTTP contract: deterministic export + semantic compatibility checking (TASK-018A).

Two things are proven here:

1. the exported contract is byte-stable, so a diff means the API really changed;
2. the checker classifies every change category the process depends on — a
   checker that misses a breaking change is worse than no checker, because it
   converts an unreviewed incompatibility into a green build.
"""

from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentrouter import contract
from agentrouter.cli import app

pytest.importorskip("fastapi")

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def doc() -> dict:
    return contract.canonical_openapi()


# --- determinism -------------------------------------------------------------


def test_export_is_byte_stable_across_runs():
    assert contract.dumps(contract.canonical_openapi()) == contract.dumps(
        contract.canonical_openapi()
    )


def test_canonical_document_drops_environment_dependent_fields(doc):
    assert "servers" not in doc  # depends on how the process was started


def test_canonical_document_sorts_keys_recursively(doc):
    assert list(doc) == sorted(doc)
    assert list(doc["paths"]) == sorted(doc["paths"])


def test_committed_contract_matches_the_live_app():
    """The committed artifact is the contract; drift must fail, not auto-heal."""
    baseline = contract.load_baseline(REPO_ROOT)
    report = contract.diff_contracts(baseline, contract.canonical_openapi())
    assert report.changes == [], f"contract drift: {report.as_dict()}"


def test_every_served_operation_is_in_the_contract(doc):
    baseline = contract.load_baseline(REPO_ROOT)
    live = {(p, m) for p, ops in doc["paths"].items() for m in ops}
    committed = {(p, m) for p, ops in baseline["paths"].items() for m in ops}
    assert live == committed


# --- baseline handling -------------------------------------------------------


def test_missing_baseline_is_an_error_never_a_pass(tmp_path):
    with pytest.raises(contract.ContractError, match="no committed contract"):
        contract.load_baseline(tmp_path)


def test_unreadable_baseline_is_an_error(tmp_path):
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    openapi_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(contract.ContractError, match="unreadable"):
        contract.load_baseline(tmp_path)


def test_non_openapi_baseline_is_an_error(tmp_path):
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    openapi_path.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(contract.ContractError, match="not an OpenAPI document"):
        contract.load_baseline(tmp_path)


def test_export_writes_contract_and_manifest(tmp_path):
    path, _ = contract.export_contract(tmp_path)
    manifest = json.loads((path.parent / contract.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert path.exists()
    for key in (
        "product_version",
        "contract_version",
        "generation_command",
        "generation_tool",
        "source_commit",
        "generated_at",
        "operation_count",
    ):
        assert key in manifest


def test_contract_file_carries_no_timestamp_or_commit():
    """Provenance lives in the manifest; putting it in the contract would make
    every regeneration a diff and destroy the checker's signal."""
    text = (REPO_ROOT / contract.CONTRACT_DIR / contract.OPENAPI_FILE).read_text(encoding="utf-8")
    assert "generated_at" not in text
    assert "source_commit" not in text


# --- breaking change detection ----------------------------------------------


def _mutate(doc: dict, fn) -> dict:
    new = copy.deepcopy(doc)
    fn(new)
    return new


def _kinds(report) -> set[str]:
    return {c.kind for c in report.changes}


def test_detects_removed_endpoint(doc):
    new = _mutate(doc, lambda d: d["paths"].pop("/v1/route"))
    report = contract.diff_contracts(doc, new)
    assert not report.compatible
    assert "endpoint_removed" in _kinds(report)


def test_detects_removed_method(doc):
    new = _mutate(doc, lambda d: d["paths"]["/v1/route"].pop("post"))
    report = contract.diff_contracts(doc, new)
    assert not report.compatible and "method_removed" in _kinds(report)


def test_detects_removed_response_status(doc):
    # 4XX is documented app-wide (the error envelope); dropping it removes a
    # response clients are told to expect.
    assert "4XX" in doc["paths"]["/v1/route"]["post"]["responses"]

    def drop(d):
        d["paths"]["/v1/route"]["post"]["responses"].pop("4XX")

    report = contract.diff_contracts(doc, _mutate(doc, drop))
    assert not report.compatible and "response_status_removed" in _kinds(report)


def test_detects_removed_response_field(doc):
    def drop(d):
        d["components"]["schemas"]["HealthResponse"]["properties"].pop("status")

    report = contract.diff_contracts(doc, _mutate(doc, drop))
    assert not report.compatible and "response_field_removed" in _kinds(report)


def test_detects_optional_field_becoming_required(doc):
    def tighten(d):
        schema = d["components"]["schemas"]["RouteRequest"]
        schema.setdefault("required", []).append("prefer")

    report = contract.diff_contracts(doc, _mutate(doc, tighten))
    assert not report.compatible and "field_became_required" in _kinds(report)


def test_detects_request_type_change(doc):
    def retype(d):
        d["components"]["schemas"]["FeedbackRequest"]["properties"]["rating"]["type"] = "string"

    report = contract.diff_contracts(doc, _mutate(doc, retype))
    assert not report.compatible and "request_type_changed" in _kinds(report)


def test_detects_response_type_change(doc):
    def retype(d):
        d["components"]["schemas"]["HealthResponse"]["properties"]["status"]["type"] = "integer"

    report = contract.diff_contracts(doc, _mutate(doc, retype))
    assert not report.compatible and "response_type_changed" in _kinds(report)


def test_detects_narrowed_enum(doc):
    baseline = _mutate(
        doc,
        lambda d: d["components"]["schemas"].__setitem__(
            "Colour", {"type": "string", "enum": ["red", "green"]}
        ),
    )
    narrowed = _mutate(
        baseline,
        lambda d: d["components"]["schemas"]["Colour"].__setitem__("enum", ["red"]),
    )
    # reference the schema from a real response so the walker reaches it
    for d in (baseline, narrowed):
        d["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ] = {"$ref": "#/components/schemas/Colour"}
    # This one is wired into a RESPONSE, where promising fewer values is safe.
    report = contract.diff_contracts(baseline, narrowed)
    assert report.compatible and "enum_narrowed" in _kinds(report)


def test_narrowing_a_request_enum_is_breaking(doc):
    """The direction that matters: fewer accepted values rejects existing callers."""

    def narrow(d):
        d["components"]["schemas"]["Level"]["enum"] = ["high", "low"]

    report = contract.diff_contracts(doc, _mutate(doc, narrow))
    assert not report.compatible and "enum_narrowed" in _kinds(report)


def test_the_app_really_declares_authentication(doc):
    """Auth must be a declared security scheme, not a bare header parameter.

    A bare ``X-API-Key`` Header looks like an ordinary optional parameter in the
    export, so adding or removing authentication on an endpoint would be
    invisible to the checker below. This asserts the surface the next test
    depends on actually exists.
    """
    assert "APIKeyHeader" in doc["components"]["securitySchemes"]
    assert doc["paths"]["/v1/route"]["post"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in doc["paths"]["/health"]["get"]  # probes stay open


def test_detects_changed_authentication_requirement(doc):
    def swap_scheme(d):
        d["paths"]["/v1/route"]["post"]["security"] = [{"NewScheme": []}]

    report = contract.diff_contracts(doc, _mutate(doc, swap_scheme))
    assert not report.compatible and "authentication_changed" in _kinds(report)

    def drop_auth(d):
        d["paths"]["/v1/route"]["post"].pop("security")

    report2 = contract.diff_contracts(doc, _mutate(doc, drop_auth))
    assert not report2.compatible and "authentication_removed" in _kinds(report2)


def test_untyped_response_would_leave_the_contract_blind(doc):
    """Every operation must document a response schema, not just 'an object'.

    Four operations were once declared ``-> dict``. The export then said only
    ``{}`` for their 200 body, so renaming or removing a field on them produced
    no diff at all — the gate was green while the API broke.
    """
    for path, ops in doc["paths"].items():
        for method, op in ops.items():
            ok = op["responses"].get("200") or op["responses"].get("201")
            if not ok or "content" not in ok:
                continue
            schema = ok["content"]["application/json"]["schema"]
            assert schema not in ({}, {"type": "object"}), f"{method.upper()} {path} is untyped"


def test_detects_incompatible_error_schema(doc):
    def break_error(d):
        d["components"]["schemas"]["ErrorBody"]["properties"].pop("code")

    report = contract.diff_contracts(doc, _mutate(doc, break_error))
    assert not report.compatible and "response_field_removed" in _kinds(report)


def test_detects_path_parameter_requirement_change(doc):
    def loosen(d):
        for p in d["paths"]["/v1/decisions/{decision_id}"]["get"]["parameters"]:
            p["required"] = False

    report = contract.diff_contracts(doc, _mutate(doc, loosen))
    assert "parameter_became_optional" in _kinds(report)

    def remove(d):
        d["paths"]["/v1/decisions/{decision_id}"]["get"]["parameters"] = []

    report2 = contract.diff_contracts(doc, _mutate(doc, remove))
    assert not report2.compatible and "parameter_removed" in _kinds(report2)


def test_detects_newly_required_parameter(doc):
    def add(d):
        d["paths"]["/v1/models"]["get"]["parameters"] = [
            {"name": "since", "in": "query", "required": True, "schema": {"type": "string"}}
        ]

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert not report.compatible and "required_parameter_added" in _kinds(report)


# --- additive / risky classification ----------------------------------------


def test_new_endpoint_is_additive(doc):
    def add(d):
        d["paths"]["/v1/brand-new"] = {"get": {"responses": {"200": {"description": "ok"}}}}

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "endpoint_added" in _kinds(report)


def test_new_optional_response_field_is_additive(doc):
    def add(d):
        d["components"]["schemas"]["HealthResponse"]["properties"]["uptime"] = {"type": "number"}

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "response_field_added" in _kinds(report)


def test_new_optional_request_field_is_additive(doc):
    def add(d):
        d["components"]["schemas"]["RouteRequest"]["properties"]["hint"] = {"type": "string"}

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "optional_request_field_added" in _kinds(report)


def test_new_documented_response_is_additive(doc):
    def add(d):
        d["paths"]["/health"]["get"]["responses"]["503"] = {"description": "unavailable"}

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "response_status_added" in _kinds(report)


def test_enum_expansion_is_risky_not_breaking(doc):
    baseline = copy.deepcopy(doc)
    baseline["components"]["schemas"]["Colour"] = {"type": "string", "enum": ["red"]}
    expanded = copy.deepcopy(baseline)
    expanded["components"]["schemas"]["Colour"]["enum"] = ["red", "green"]
    for d in (baseline, expanded):
        d["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ] = {"$ref": "#/components/schemas/Colour"}
    report = contract.diff_contracts(baseline, expanded)
    assert report.compatible and "enum_expanded" in _kinds(report)


def test_default_and_format_changes_are_risky(doc):
    def change(d):
        props = d["components"]["schemas"]["RouteRequest"]["properties"]
        props["no_log"]["default"] = True

    report = contract.diff_contracts(doc, _mutate(doc, change))
    assert report.compatible and "default_changed" in _kinds(report)


def test_documented_semantics_change_is_risky(doc):
    def change(d):
        d["paths"]["/v1/route"]["post"]["description"] = "completely different meaning"

    report = contract.diff_contracts(doc, _mutate(doc, change))
    assert report.compatible and "documented_semantics_changed" in _kinds(report)


def test_identical_documents_produce_no_changes(doc):
    assert contract.diff_contracts(doc, copy.deepcopy(doc)).changes == []


def test_report_serialises_deterministically(doc):
    new = _mutate(doc, lambda d: d["paths"].pop("/v1/route"))
    payload = contract.diff_contracts(doc, new).as_dict()
    assert payload["compatible"] is False
    assert payload["counts"]["breaking"] >= 1
    assert json.dumps(payload)  # JSON-serialisable


# --- CLI ---------------------------------------------------------------------


def test_cli_check_passes_against_the_committed_contract(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(REPO_ROOT))
    r = runner.invoke(app, ["contract", "check"])
    assert r.exit_code == 0, r.output


def test_cli_check_json_is_machine_readable(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(REPO_ROOT))
    r = runner.invoke(app, ["contract", "check", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["compatible"] is True and "counts" in payload


def test_cli_check_without_a_baseline_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "check"])
    assert r.exit_code == 3  # EXIT_REGISTRY: missing baseline is never success


def test_cli_check_reports_breaking_change_with_exit_1(monkeypatch, tmp_path):
    """A baseline promising an endpoint the app no longer serves must fail CI."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/removed-since"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    openapi_path.write_text(contract.dumps(inflated), encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "check"])
    assert r.exit_code == 1
    assert "endpoint_removed" in r.output


def test_cli_export_refuses_to_erase_a_breaking_change(monkeypatch, tmp_path):
    """The baseline must not be silently regenerated over an incompatibility."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/removed-since"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    before = contract.dumps(inflated)
    openapi_path.write_text(before, encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "export"])
    assert r.exit_code == 1
    assert "Refusing to update the baseline" in r.output
    assert openapi_path.read_text(encoding="utf-8") == before  # untouched


def test_cli_export_accepts_a_reviewed_breaking_change(monkeypatch, tmp_path):
    openapi_path, manifest_path = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/removed-since"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    openapi_path.write_text(contract.dumps(inflated), encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(
        app,
        ["contract", "export", "--accept-breaking", "--reason", "v2 drops the legacy path"],
    )
    assert r.exit_code == 0, r.output
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    history = manifest["accepted_breaking_changes"]
    assert [e["reason"] for e in history] == ["v2 drops the legacy path"]
    # The recorded changes are the ones the checker actually found, not the
    # operator's assertion about them.
    assert any(c["kind"] == "endpoint_removed" for c in history[0]["changes"])


def test_cli_export_accept_breaking_requires_a_reason(monkeypatch, tmp_path):
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/removed-since"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    openapi_path.write_text(contract.dumps(inflated), encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "export", "--accept-breaking"])
    assert r.exit_code == 2
    assert "requires --reason" in r.output


def test_cli_check_writes_a_report_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(REPO_ROOT))
    out = tmp_path / "reports" / "compat.json"
    r = runner.invoke(app, ["contract", "check", "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert json.loads(out.read_text(encoding="utf-8"))["compatible"] is True


def test_missing_server_extra_fails_with_guidance_not_a_traceback(monkeypatch):
    """The REST surface is an optional extra; its absence must be explained."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("fastapi") or name.endswith("server.app"):
            raise ModuleNotFoundError("No module named 'fastapi'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(__import__("sys").modules, "agentrouter.server.app", raising=False)
    with pytest.raises(contract.ServerExtraMissing, match=r"server extra"):
        contract.canonical_openapi()


def test_missing_server_extra_is_not_reported_as_a_missing_baseline(monkeypatch, tmp_path):
    """Two different failures must not share an exit code or a fix.

    A core-only install has no API to describe, so telling the user to run
    `contract export` — which fails identically — sends them in a circle. Only a
    genuinely missing baseline gets exit 3 and that instruction.
    """
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        contract,
        "check",
        lambda *a, **k: (_ for _ in ()).throw(
            contract.ServerExtraMissing("needs the server extra")
        ),
    )
    r = runner.invoke(app, ["contract", "check"])
    # Its own code: not 1 (a real breaking change) and not 3 (a missing baseline).
    assert r.exit_code == 4
    assert "server extra" in r.output
    assert "contract export" not in r.output


# --- the checker cannot be defeated ------------------------------------------
#
# A compatibility gate is only worth its CI minutes if it cannot be turned green
# by editing the thing it checks. Each test below corresponds to a way the gate
# was bypassable during review.


def test_a_dangling_ref_in_the_baseline_is_rejected_not_compared(tmp_path):
    """One-character ref edits used to inline as `{}` and hide every field."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    sabotaged = contract.canonical_openapi()
    sabotaged["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/DoesNotExist"}
    openapi_path.write_text(contract.dumps(sabotaged), encoding="utf-8")

    assert contract.validate_refs(sabotaged) == ["#/components/schemas/DoesNotExist (unresolvable)"]
    with pytest.raises(contract.ContractError, match="unusable"):
        contract.load_baseline(tmp_path)


def test_a_self_referential_ref_is_rejected(doc):
    doc["components"]["schemas"]["Loop"] = {"$ref": "#/components/schemas/Loop"}
    doc["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/Loop"
    }
    assert any("self-referential" in b for b in contract.validate_refs(doc))


def test_a_remote_ref_is_rejected(doc):
    doc["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "https://example.invalid/schema.json"
    }
    assert any("only local refs" in b for b in contract.validate_refs(doc))


def test_ref_expansion_is_bounded_rather_than_exhausting_memory(doc):
    """Fan-out refs multiply on inlining; the checker must fail loudly, not OOM.

    Also a performance regression test: validating this document walked every
    path separately before memoisation, which is 2**26 steps — CI would hang on
    a contract small enough to review by eye. It must now finish immediately.
    """
    schemas = doc["components"]["schemas"]
    schemas["Fan0"] = {"type": "string"}
    for i in range(1, 27):
        prev = f"#/components/schemas/Fan{i - 1}"
        schemas[f"Fan{i}"] = {
            "type": "object",
            "properties": {"a": {"$ref": prev}, "b": {"$ref": prev}},
        }
    doc["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/Fan26"
    }
    assert contract.validate_refs(doc) == []  # every ref is legitimate
    with pytest.raises(contract.ContractError, match="too large or nested too deeply"):
        contract.diff_contracts(doc, copy.deepcopy(doc))


def test_export_refuses_to_write_through_a_symlink(tmp_path):
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    victim = tmp_path / "victim.json"
    victim.write_text("keep me", encoding="utf-8")
    openapi_path.symlink_to(victim)

    with pytest.raises(contract.ContractError, match="symlink"):
        contract.export_contract(tmp_path)
    assert victim.read_text(encoding="utf-8") == "keep me"


def test_export_refuses_to_write_outside_the_root(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    (root / contract.CONTRACT_DIR).mkdir(parents=True)
    outside.mkdir()
    # A symlinked contract *directory* resolves out of the root.
    (root / contract.CONTRACT_DIR).rmdir()
    (root / contract.CONTRACT_DIR).symlink_to(outside, target_is_directory=True)

    with pytest.raises(contract.ContractError, match="refusing to write"):
        contract.export_contract(root)


def test_export_cannot_erase_a_previous_acceptance(monkeypatch, tmp_path):
    """The audit trail is append-only; a routine export must not clear it."""
    openapi_path, manifest_path = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/gone"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    openapi_path.write_text(contract.dumps(inflated), encoding="utf-8")
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))

    accepted = runner.invoke(
        app, ["contract", "export", "--accept-breaking", "--reason", "dropped /v1/gone"]
    )
    assert accepted.exit_code == 0, accepted.output

    # Second, entirely routine export: no breaking change this time.
    again = runner.invoke(app, ["contract", "export"])
    assert again.exit_code == 0, again.output
    history = json.loads(manifest_path.read_text(encoding="utf-8"))["accepted_breaking_changes"]
    assert [e["reason"] for e in history] == ["dropped /v1/gone"]


def test_export_cannot_record_a_breaking_change_that_did_not_happen(monkeypatch, tmp_path):
    """--accept-breaking on a compatible export must not fabricate provenance."""
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    assert runner.invoke(app, ["contract", "export"]).exit_code == 0  # clean baseline
    r = runner.invoke(
        app, ["contract", "export", "--accept-breaking", "--reason", "pretending we broke v1"]
    )
    assert r.exit_code == 0, r.output
    _, manifest_path = contract.contract_paths(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "accepted_breaking_changes" not in manifest


# --- categories the checker used to miss entirely -----------------------------


def test_detects_a_tightened_parameter_schema(doc):
    """Parameter schemas were compared for presence only, never for shape."""

    def retype(d):
        for p in d["paths"]["/v1/decisions/{decision_id}"]["get"]["parameters"]:
            p["schema"] = {"type": "integer"}

    report = contract.diff_contracts(doc, _mutate(doc, retype))
    assert not report.compatible and "request_type_changed" in _kinds(report)


def test_detects_a_narrowed_request_constraint(doc):
    baseline = _mutate(
        doc,
        lambda d: d["components"]["schemas"]["RouteRequest"]["properties"]["task"].__setitem__(
            "maxLength", 1000
        ),
    )
    narrowed = _mutate(
        baseline,
        lambda d: d["components"]["schemas"]["RouteRequest"]["properties"]["task"].__setitem__(
            "maxLength", 10
        ),
    )
    report = contract.diff_contracts(baseline, narrowed)
    assert not report.compatible and "constraint_tightened" in _kinds(report)


def test_relaxing_a_request_constraint_is_additive(doc):
    baseline = _mutate(
        doc,
        lambda d: d["components"]["schemas"]["RouteRequest"]["properties"]["task"].__setitem__(
            "maxLength", 10
        ),
    )
    relaxed = _mutate(
        baseline,
        lambda d: d["components"]["schemas"]["RouteRequest"]["properties"]["task"].__setitem__(
            "maxLength", 1000
        ),
    )
    report = contract.diff_contracts(baseline, relaxed)
    assert report.compatible and "constraint_relaxed" in _kinds(report)


def test_detects_a_removed_media_type(doc):
    def drop(d):
        d["paths"]["/v1/route"]["post"]["requestBody"]["content"] = {
            "application/cbor": {"schema": {"type": "object"}}
        }

    report = contract.diff_contracts(doc, _mutate(doc, drop))
    assert not report.compatible and "media_type_removed" in _kinds(report)


def test_detects_a_relocated_server(doc):
    """Moving the API under a prefix breaks every existing client URL."""
    relocated = _mutate(doc, lambda d: d.__setitem__("servers", [{"url": "/api/v2"}]))
    report = contract.diff_contracts(doc, relocated)
    assert not report.compatible and "servers_changed" in _kinds(report)


def test_detects_an_api_version_change(doc):
    bumped = _mutate(doc, lambda d: d["info"].__setitem__("version", "2"))
    report = contract.diff_contracts(doc, bumped)
    assert "api_version_changed" in _kinds(report)


def test_detects_a_renamed_operation_id(doc):
    """Generated SDKs name their methods after operationId."""

    def rename(d):
        d["paths"]["/v1/route"]["post"]["operationId"] = "route_v2"

    report = contract.diff_contracts(doc, _mutate(doc, rename))
    assert "operation_id_changed" in _kinds(report)


def test_detects_a_deprecation(doc):
    def deprecate(d):
        d["paths"]["/v1/route"]["post"]["deprecated"] = True

    report = contract.diff_contracts(doc, _mutate(doc, deprecate))
    assert report.compatible and "deprecation_changed" in _kinds(report)


def test_introducing_a_bound_where_there_was_none_is_breaking(doc):
    """An absent bound is the unbounded end of the range, not 'unknown'."""

    def add_bound(d):
        d["components"]["schemas"]["RouteRequest"]["properties"]["task"]["maxLength"] = 10

    report = contract.diff_contracts(doc, _mutate(doc, add_bound))
    assert not report.compatible and "constraint_tightened" in _kinds(report)


def test_removing_a_bound_is_additive(doc):
    bounded = _mutate(
        doc,
        lambda d: d["components"]["schemas"]["RouteRequest"]["properties"]["task"].__setitem__(
            "maxLength", 10
        ),
    )
    report = contract.diff_contracts(bounded, doc)
    assert report.compatible and "constraint_relaxed" in _kinds(report)


# --- blind spots found by the independent backward-compatibility review -------
#
# Every case below was a MISCLASSIFICATION, verified by mutating the real
# exported document. The false greens matter most: each one was a breaking
# change the gate waved through.


def test_sees_through_the_nullable_wrapper(doc):
    """FastAPI renders every ``T | None`` as ``anyOf[T, null]`` — which is most
    of this API. Comparing only the union node left the interior unprotected."""

    def narrow_enum(d):
        d["components"]["schemas"]["Level"]["enum"] = ["low", "medium"]

    report = contract.diff_contracts(doc, _mutate(doc, narrow_enum))
    assert not report.compatible and "enum_narrowed" in _kinds(report)

    def tighten_nested(d):
        prop = d["components"]["schemas"]["ClassifyRequest"]["properties"]["context_tokens"]
        prop["anyOf"][0]["exclusiveMinimum"] = 1000

    report2 = contract.diff_contracts(doc, _mutate(doc, tighten_nested))
    assert not report2.compatible and "constraint_tightened" in _kinds(report2)


def test_detects_a_redefined_security_scheme(doc):
    """The requirement can stay `APIKeyHeader` while the scheme itself moves the
    credential to another header — every existing client stops authenticating."""

    def rename_header(d):
        d["components"]["securitySchemes"]["APIKeyHeader"]["name"] = "Authorization"

    report = contract.diff_contracts(doc, _mutate(doc, rename_header))
    assert not report.compatible and "security_scheme_changed" in _kinds(report)

    def change_type(d):
        d["components"]["securitySchemes"]["APIKeyHeader"] = {"type": "http", "scheme": "bearer"}

    report2 = contract.diff_contracts(doc, _mutate(doc, change_type))
    assert not report2.compatible and "security_scheme_changed" in _kinds(report2)


def test_a_new_required_response_field_is_additive(doc):
    """A gate that cries wolf gets bypassed.

    FastAPI marks every non-defaulted response field required, so adding a field
    to a response — the most common additive change there is — used to fail CI
    and force `--accept-breaking`. `required` on a response is a promise from the
    server, not an obligation on the client.
    """

    def add(d):
        schema = d["components"]["schemas"]["ModelSummary"]
        schema["properties"]["tier"] = {"type": "string", "title": "Tier"}
        schema["required"].append("tier")

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "response_field_added" in _kinds(report)


def test_a_response_field_becoming_optional_is_breaking(doc):
    """The mirror image: withdrawing a guarantee the server used to make."""

    def relax(d):
        d["components"]["schemas"]["ModelSummary"]["required"].remove("model_id")

    report = contract.diff_contracts(doc, _mutate(doc, relax))
    assert not report.compatible and "field_became_optional" in _kinds(report)


def test_an_additional_accepted_auth_scheme_is_additive(doc):
    """`security` entries are alternatives (OR): a second one breaks nobody."""

    def add(d):
        d["components"]["securitySchemes"]["Bearer"] = {"type": "http", "scheme": "bearer"}
        d["paths"]["/v1/route"]["post"]["security"].append({"Bearer": []})

    report = contract.diff_contracts(doc, _mutate(doc, add))
    assert report.compatible and "authentication_alternative_added" in _kinds(report)


def test_removing_authentication_entirely_is_reported_distinctly(doc):
    def unprotect(d):
        d["paths"]["/v1/route"]["post"].pop("security")

    report = contract.diff_contracts(doc, _mutate(doc, unprotect))
    assert not report.compatible and "authentication_removed" in _kinds(report)


def test_nullability_direction_is_classified_per_side(doc):
    """A request accepting null is permissive; a response returning it is not."""

    # Change ONLY nullability: keep every sibling keyword (the field carries a
    # maxLength) so the report isolates the one variable under test.
    def drop_null(d):
        prop = d["components"]["schemas"]["FeedbackRequest"]["properties"]["note"]
        payload = next(b for b in prop["anyOf"] if b.get("type") != "null")
        prop.pop("anyOf")
        prop.update(payload)

    strict = _mutate(doc, drop_null)
    # request gains null -> additive
    report = contract.diff_contracts(strict, doc)
    assert report.compatible and "became_nullable" in _kinds(report)
    # request loses null -> breaking
    report2 = contract.diff_contracts(doc, strict)
    assert not report2.compatible and "became_non_nullable" in _kinds(report2)


def test_check_can_compare_against_an_arbitrary_baseline(tmp_path):
    """CI compares against the PR *base*, so deleting the committed contract
    cannot turn a breaking change green — the base still remembers it."""
    base = tmp_path / "base.json"
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/since-removed"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    base.write_text(contract.dumps(inflated), encoding="utf-8")

    report, _ = contract.check(REPO_ROOT, baseline_path=base)
    assert not report.compatible
    assert any(c.kind == "endpoint_removed" for c in report.breaking)


def test_cli_baseline_flag_detects_what_the_committed_contract_no_longer_does(
    monkeypatch, tmp_path
):
    base = tmp_path / "base.json"
    inflated = contract.canonical_openapi()
    inflated["paths"]["/v1/since-removed"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    base.write_text(contract.dumps(inflated), encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(REPO_ROOT))
    clean = runner.invoke(app, ["contract", "check"])
    assert clean.exit_code == 0, "the committed contract is in sync"

    against_base = runner.invoke(app, ["contract", "check", "--baseline", str(base)])
    assert against_base.exit_code == 1
    assert "endpoint_removed" in against_base.output


def test_export_refuses_to_write_through_a_hardlink(tmp_path):
    """A hardlink is invisible to is_symlink() and resolves inside the root."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    victim = tmp_path / "victim.json"
    victim.write_text("keep me", encoding="utf-8")
    try:
        os.link(victim, openapi_path)
    except OSError:  # pragma: no cover - filesystem without hardlinks
        pytest.skip("hardlinks unsupported here")

    with pytest.raises(contract.ContractError, match="hardlink"):
        contract.export_contract(tmp_path)
    assert victim.read_text(encoding="utf-8") == "keep me"


# --- second review round: bypasses and bounds -------------------------------


def test_an_unreadable_baseline_is_not_treated_as_a_missing_one(monkeypatch, tmp_path):
    """Corrupting the baseline must not do what deleting it is refused for.

    `export` may proceed silently on a genuine first export. If an unparseable
    baseline also counted as "missing", corrupting the file would bypass the
    breaking-change refusal and overwrite it with exit 0.
    """
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    openapi_path.write_text("{not json", encoding="utf-8")
    before = openapi_path.read_bytes()

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "export"])
    assert r.exit_code == 3, r.output
    assert "Refusing to overwrite an unreadable baseline" in r.output
    assert openapi_path.read_bytes() == before


def test_a_genuinely_absent_baseline_still_allows_a_first_export(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    r = runner.invoke(app, ["contract", "export"])
    assert r.exit_code == 0, r.output
    openapi_path, _ = contract.contract_paths(tmp_path)
    assert openapi_path.exists()


def test_missing_and_unreadable_baselines_raise_distinct_types(tmp_path):
    with pytest.raises(contract.BaselineMissing):
        contract.load_baseline(tmp_path)

    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    openapi_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(contract.ContractError) as excinfo:
        contract.load_baseline(tmp_path)
    assert not isinstance(excinfo.value, contract.BaselineMissing)


def test_a_deeply_nested_baseline_fails_cleanly_not_with_a_traceback(monkeypatch, tmp_path):
    """Pathological nesting blows the stack inside json.loads itself."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    depth = 60_000
    openapi_path.write_text(
        '{"openapi":"3.1.0","info":{"title":"t","version":"1"},"paths":{"/x":{"get":'
        '{"responses":{"200":{"description":"ok"}}}}},"components":{"schemas":{"Deep":'
        + '{"properties":{"a":' * depth
        + '{"type":"string"}'
        + "}}" * depth
        + "}}}",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    for command, expected in (("check", 3), ("export", 3)):
        r = runner.invoke(app, ["contract", command])
        assert r.exit_code == expected, f"{command}: {r.output}"
        assert "Traceback" not in r.output and "RecursionError" not in r.output


def _fanout(paths: int, chain: int) -> dict:
    """A document whose refs re-expand exponentially when inlined."""
    schemas: dict = {"Fan0": {"type": "string"}}
    for i in range(1, chain + 1):
        prev = f"#/components/schemas/Fan{i - 1}"
        schemas[f"Fan{i}"] = {
            "type": "object",
            "properties": {"a": {"$ref": prev}, "b": {"$ref": prev}},
        }
    doc: dict = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "components": {"schemas": schemas},
        "paths": {},
    }
    for p in range(paths):
        doc["paths"][f"/p{p}"] = {
            "get": {
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/Fan{chain}"}
                            }
                        },
                    }
                }
            }
        }
    return doc


@pytest.mark.parametrize("paths", [1, 16, 256])
def test_comparison_cost_is_bounded_by_one_budget_for_the_whole_run(paths):
    """The budget must bound the RUN, not each call.

    `_resolve` used to allocate a fresh budget on every entry while the traversal
    re-entered it per property, so total work grew with the number of shared
    operations — 73s from an 11 KB crafted file, scaling linearly with path
    count. One shared counter makes the advertised ceiling real.
    """
    doc = _fanout(paths, 14)
    started = time.perf_counter()
    with pytest.raises(contract.ContractError, match="too large|too deeply nested"):
        contract.diff_contracts(doc, copy.deepcopy(doc))
    assert time.perf_counter() - started < 10, "refusal must be fast regardless of size"


def _deeply_nested(levels: int) -> dict:
    """A ref-free document nested past the comparison depth ceiling.

    Built fresh on each call rather than deep-copied: ``copy.deepcopy`` overflows
    the stack on this shape before the checker is ever reached, which would test
    CPython's recursion limit instead of the gate.
    """
    deep: dict = {"type": "object"}
    node = deep
    for _ in range(levels):
        node["properties"] = {"a": {"type": "object"}}
        node = node["properties"]["a"]
    return {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/x": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": deep}},
                        }
                    }
                }
            }
        },
    }


def test_deep_nesting_without_refs_is_also_bounded():
    """`_compare_schema` recurses through properties independently of $ref, so it
    needs its own ceiling — a ref-free document can still overflow the stack."""
    with pytest.raises(contract.ContractError, match="nested too deeply|too deeply to compare"):
        contract.diff_contracts(_deeply_nested(500), _deeply_nested(500))


# --- third review round: classification correctness ---------------------------
#
# Every case below was a MISCLASSIFICATION found by mutating the real exported
# document. False greens are the dangerous kind (a break waved through); false
# reds erode the gate until someone routes around it. Both are bugs.


def _payload_branch(prop: dict) -> dict:
    """The non-null branch of an `anyOf` (canonicalisation sorts `null` first)."""
    return next(b for b in prop["anyOf"] if b.get("type") != "null")


def test_introducing_an_enum_on_a_free_form_request_field_is_breaking(doc):
    """The most extreme narrowing there is: every unlisted value now 422s.

    The comparison used to require an enum on BOTH sides, so introducing one
    reported nothing at all.
    """

    def constrain(d):
        _payload_branch(d["components"]["schemas"]["RouteRequest"]["properties"]["prefer"]).update(
            {"enum": ["fast", "cheap"]}
        )

    report = contract.diff_contracts(doc, _mutate(doc, constrain))
    assert not report.compatible and "enum_introduced" in _kinds(report)


def test_const_is_compared_like_a_one_value_enum(doc):
    """pydantic emits `const` for `Literal[...]`, so this is reachable from our
    own toolchain — not a theoretical OpenAPI corner."""

    def pin(d):
        _payload_branch(d["components"]["schemas"]["RouteRequest"]["properties"]["prefer"]).update(
            {"const": "fast"}
        )

    report = contract.diff_contracts(doc, _mutate(doc, pin))
    assert not report.compatible and "enum_introduced" in _kinds(report)


def test_removing_an_enum_is_reported_even_though_it_is_not_breaking(doc):
    """`Level` is reachable from both a request and a response. Dropping the
    constraint accepts more on the way in (additive) and may return more on the
    way out (risky) — either way it must not be silent."""
    report = contract.diff_contracts(
        doc, _mutate(doc, lambda d: d["components"]["schemas"]["Level"].pop("enum"))
    )
    assert "enum_removed" in _kinds(report)


def test_allof_is_a_conjunction_not_a_union(doc):
    """More `anyOf` branches is more permissive; more `allOf` branches is less.
    Treating them alike classified every `allOf` change backwards."""

    def narrow(d):
        d["components"]["schemas"]["ClassifyRequest"]["properties"]["risk"] = {
            "allOf": [{"$ref": "#/components/schemas/Level"}, {"enum": ["low"]}]
        }

    report = contract.diff_contracts(doc, _mutate(doc, narrow))
    assert not report.compatible and "union_narrowed" in _kinds(report)

    # ...and the reverse relaxes the request
    wide = _mutate(doc, narrow)
    relaxed = copy.deepcopy(wide)
    relaxed["components"]["schemas"]["ClassifyRequest"]["properties"]["risk"] = {
        "allOf": [{"$ref": "#/components/schemas/Level"}]
    }
    back = contract.diff_contracts(wide, relaxed)
    assert back.compatible and "union_widened" in _kinds(back)


def test_type_erasure_is_reported_not_silent(doc):
    """A field that stops declaring its type constrains nothing. `_type_of`
    returns None for that, so a plain both-sides-truthy check skipped it."""

    def erase(d):
        d["components"]["schemas"]["ModelSummary"]["properties"]["context_window"] = {
            "title": "Context Window"
        }

    report = contract.diff_contracts(doc, _mutate(doc, erase))
    assert "type_erased" in _kinds(report)


def test_openapi_31_list_form_type_is_compared(doc):
    """The document declares 3.1, where `type: ["integer","null"]` is legal — and
    the baseline is a hand-editable file, so not reading it would be a one-edit
    way to switch off type checking."""

    def retype(d):
        d["components"]["schemas"]["ModelSummary"]["properties"]["key"]["type"] = ["integer"]

    report = contract.diff_contracts(doc, _mutate(doc, retype))
    assert not report.compatible and "response_type_changed" in _kinds(report)


def test_request_body_becoming_required_is_breaking(doc):
    """Only `content` was read, so this was invisible."""
    optional = _mutate(
        doc, lambda d: d["paths"]["/v1/route"]["post"]["requestBody"].__setitem__("required", False)
    )
    report = contract.diff_contracts(optional, doc)
    assert not report.compatible and "request_body_became_required" in _kinds(report)


def test_oauth2_flow_endpoints_are_compared(doc):
    """For oauth2 the credential source lives entirely in `flows`, so comparing
    only type/name/in/scheme would miss a repointed authorization endpoint."""
    scheme = {
        "type": "oauth2",
        "flows": {
            "authorizationCode": {
                "authorizationUrl": "https://example.test/authorize",
                "scopes": {},
            }
        },
    }
    before = _mutate(doc, lambda d: d["components"]["securitySchemes"].__setitem__("OAuth", scheme))
    after = copy.deepcopy(before)
    after["components"]["securitySchemes"]["OAuth"]["flows"]["authorizationCode"][
        "authorizationUrl"
    ] = "https://elsewhere.test/authorize"
    report = contract.diff_contracts(before, after)
    assert not report.compatible and "security_scheme_changed" in _kinds(report)


def test_additional_properties_as_a_schema_can_close_a_request(doc):
    """`False` is not the only way to reject previously-valid extra properties."""

    def constrain(d):
        d["components"]["schemas"]["RouteRequest"]["additionalProperties"] = {"type": "integer"}

    report = contract.diff_contracts(doc, _mutate(doc, constrain))
    assert not report.compatible and "additional_properties_closed" in _kinds(report)


def test_a_new_request_format_is_breaking_like_a_new_pattern(doc):
    """pydantic enforces `format` on input, so `uuid` rejects what used to pass.
    Treating it as merely risky while `pattern` was breaking was inconsistent."""

    def tighten(d):
        d["components"]["schemas"]["FeedbackRequest"]["properties"]["decision_id"]["format"] = (
            "uuid"
        )

    report = contract.diff_contracts(doc, _mutate(doc, tighten))
    assert not report.compatible and "format_changed" in _kinds(report)


# --- false reds: a gate that cries wolf gets routed around --------------------


def test_reordering_union_branches_is_not_a_change(doc):
    """Branch order is not semantic. Without canonical sorting, a library upgrade
    that reorders union members turns CI red on a byte-equivalent API."""

    def shuffle(d):
        prop = d["components"]["schemas"]["RouteRequest"]["properties"]["prefer"]
        prop["anyOf"] = list(reversed(prop["anyOf"]))

    report = contract.diff_contracts(doc, _mutate(doc, shuffle))
    assert report.changes == []


def test_widening_a_request_union_is_additive(doc):
    def two(d):
        d["components"]["schemas"]["RouteRequest"]["properties"]["prefer"] = {
            "oneOf": [{"type": "string"}, {"type": "integer"}]
        }

    def three(d):
        d["components"]["schemas"]["RouteRequest"]["properties"]["prefer"] = {
            "oneOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]
        }

    report = contract.diff_contracts(_mutate(doc, two), _mutate(doc, three))
    assert report.compatible and "union_widened" in _kinds(report)


def test_replacing_a_status_wildcard_with_explicit_codes_is_not_a_removal(doc):
    """`4XX` -> `401/404/422` documents MORE, not less. Flagging it as a removed
    response made a documentation improvement fail CI."""

    def refine(d):
        responses = d["paths"]["/v1/route"]["post"]["responses"]
        wildcard = responses.pop("4XX")
        for code in ("401", "404", "422"):
            responses[code] = copy.deepcopy(wildcard)

    report = contract.diff_contracts(doc, _mutate(doc, refine))
    assert report.compatible
    assert "response_status_removed" not in _kinds(report)
    assert "response_status_refined" in _kinds(report)


# --- the acceptance workflow must be able to complete -------------------------


def _repo_with_baseline(tmp_path, extra_path: str | None = None):
    """A contract root whose baseline optionally documents an extra endpoint."""
    openapi_path, _ = contract.contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    doc = contract.canonical_openapi()
    if extra_path:
        doc["paths"][extra_path] = {"get": {"responses": {"200": {"description": "ok"}}}}
    openapi_path.write_text(contract.dumps(doc), encoding="utf-8")
    return openapi_path, doc


def test_an_owner_accepted_break_can_actually_merge(monkeypatch, tmp_path):
    """Without this the documented workflow is a dead end.

    `export --accept-breaking` moves the branch baseline, so the in-branch check
    goes green — but CI also compares against the BASE branch, which still holds
    the old contract and reports the same break. The change could be accepted and
    could never merge.
    """
    _repo_with_baseline(tmp_path, "/v1/legacy")
    base_copy = tmp_path / "base.json"
    openapi_path, _ = contract.contract_paths(tmp_path)
    base_copy.write_text(openapi_path.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    refused = runner.invoke(app, ["contract", "export"])
    assert refused.exit_code == 1, "a routine export must refuse the break"

    accepted = runner.invoke(
        app, ["contract", "export", "--accept-breaking", "--reason", "v1 drops /v1/legacy"]
    )
    assert accepted.exit_code == 0, accepted.output

    # The base branch still documents /v1/legacy. This is the check that blocked.
    against_base = runner.invoke(app, ["contract", "check", "--baseline", str(base_copy)])
    assert against_base.exit_code == 0, against_base.output
    assert "owner-accepted" in against_base.output


def test_an_unrecorded_break_still_fails_even_beside_an_accepted_one(monkeypatch, tmp_path):
    """An acceptance excuses exactly the break it recorded, nothing else."""
    _repo_with_baseline(tmp_path, "/v1/legacy")
    monkeypatch.setenv("AGENTROUTER_CONTRACT_ROOT", str(tmp_path))
    assert (
        runner.invoke(
            app, ["contract", "export", "--accept-breaking", "--reason", "drops /v1/legacy"]
        ).exit_code
        == 0
    )

    wider = tmp_path / "wider.json"
    doc = contract.canonical_openapi()
    doc["paths"]["/v1/legacy"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    doc["paths"]["/v1/also-gone"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    wider.write_text(contract.dumps(doc), encoding="utf-8")

    r = runner.invoke(app, ["contract", "check", "--baseline", str(wider)])
    assert r.exit_code == 1
    assert "/v1/also-gone" in r.output


def test_recorded_acceptances_reads_only_checker_findings(tmp_path):
    """The manifest cannot excuse a break the checker never reported: matching is
    on (kind, location) pairs the checker itself produced."""
    _, manifest_path = contract.contract_paths(tmp_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "accepted_breaking_changes": [
                    {
                        "reason": "r",
                        "changes": [
                            {"kind": "endpoint_removed", "location": "/v1/legacy"},
                            {"nonsense": True},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert contract.recorded_acceptances(tmp_path) == {("endpoint_removed", "/v1/legacy")}


def test_a_missing_or_broken_manifest_excuses_nothing(tmp_path):
    assert contract.recorded_acceptances(tmp_path) == set()
    _, manifest_path = contract.contract_paths(tmp_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{not json", encoding="utf-8")
    assert contract.recorded_acceptances(tmp_path) == set()
