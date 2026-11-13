"""Differential checks for the Rust OpenAPI canonicalization slice."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.contract import _canonical, canonical_openapi, dumps, validate_refs

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
