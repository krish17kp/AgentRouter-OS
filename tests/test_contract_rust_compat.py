"""Differential checks for the Rust OpenAPI canonicalization slice."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.contract import (
    BaselineMissing,
    ContractError,
    _canonical,
    canonical_openapi,
    contract_paths,
    dumps,
    load_baseline_file,
    validate_refs,
)

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _rust_canonical(value: dict) -> str:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "contract_canonicalize_from_json",
        ],
        cwd=root,
        input=json.dumps(value, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout


@pytest.mark.parametrize(
    "document",
    [
        {
            "z": {"nested": {"b": 2, "a": 1}},
            "tags": ["z", "a"],
            "required": ["z", "a"],
            "enum": ["z", "a"],
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "oneOf": [{"const": "z"}, {"const": "a"}],
            "allOf": [{"type": "object"}, {"type": "string"}],
            "parameters": [
                {"name": "z", "in": "query"},
                {"name": "a", "in": "path"},
            ],
            "examples": ["z", "a"],
        },
        {
            "info": {"title": "AgentRouter OS 🧭", "version": "1.0"},
            "paths": {"/雪": {"get": {"tags": ["z", "a"]}}},
        },
        {"anyOf": [{"const": "z"}, {"const": "é"}]},
    ],
)
def test_rust_canonical_json_matches_python(document):
    expected = dumps(_canonical(document))
    assert _rust_canonical(document) == expected


def test_rust_canonicalizes_the_live_openapi_contract_byte_for_byte():
    document = canonical_openapi()
    assert _rust_canonical(document) == dumps(document)


def _rust_invalid_refs(document: dict) -> list[str]:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "contract_refs_from_json",
        ],
        cwd=root,
        input=json.dumps(document, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    "document",
    [
        {
            "components": {"schemas": {"Item": {"type": "string"}}},
            "paths": {"/x": {"$ref": "#/components/schemas/Item"}},
        },
        {
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/A"},
                }
            },
            "paths": {
                "/x": {
                    "get": {
                        "responses": {
                            "200": {"schema": {"$ref": "#/components/schemas/Missing"}},
                            "201": {"schema": {"$ref": "#/components/schemas/Missing"}},
                        },
                        "parameters": [{"schema": {"$ref": "https://example.test/schema.json"}}],
                    }
                }
            },
        },
    ],
)
def test_rust_reference_validation_matches_python(document):
    assert _rust_invalid_refs(document) == validate_refs(document)


def _rust_load_baseline(path: Path) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "contract_baseline_from_file",
            "--",
            str(path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def test_rust_loads_the_committed_baseline_exactly():
    path, _ = contract_paths(Path(__file__).resolve().parents[1])
    process = _rust_load_baseline(path)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == load_baseline_file(path)


def test_rust_baseline_loader_fails_closed_like_python(tmp_path):
    openapi_path, _ = contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)

    with pytest.raises(BaselineMissing):
        load_baseline_file(openapi_path)
    missing = _rust_load_baseline(openapi_path)
    assert missing.returncode != 0
    assert missing.stderr.startswith("missing:")
    assert "no committed contract" in missing.stderr

    openapi_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="unreadable"):
        load_baseline_file(openapi_path)
    unreadable = _rust_load_baseline(openapi_path)
    assert unreadable.returncode != 0
    assert unreadable.stderr.startswith("unreadable:")

    openapi_path.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(ContractError, match="not an OpenAPI document"):
        load_baseline_file(openapi_path)
    not_openapi = _rust_load_baseline(openapi_path)
    assert not_openapi.returncode != 0
    assert not_openapi.stderr.startswith("not_openapi:")


def test_rust_baseline_loader_rejects_untrusted_references(tmp_path):
    openapi_path, _ = contract_paths(tmp_path)
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "paths": {},
        "components": {"schemas": {"Unsafe": {"$ref": "https://example.test/schema.json"}}},
    }
    openapi_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ContractError, match=r"unusable \$ref"):
        load_baseline_file(openapi_path)
    process = _rust_load_baseline(openapi_path)
    assert process.returncode != 0
    assert process.stderr.startswith("invalid_references:")
    assert "only local refs are supported" in process.stderr
