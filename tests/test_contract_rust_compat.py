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
    diff_contracts,
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


def _rust_surface_diff(old: dict, new: dict) -> dict:
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
            "contract_surface_diff_from_json",
        ],
        cwd=root,
        input=json.dumps({"old": old, "new": new}, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            {"info": {"version": "1.0"}, "paths": {}},
            {"info": {"version": "2.0"}, "paths": {"/new": {"get": {}}}},
        ),
        (
            {"paths": {"/x": {"get": {}, "post": {}}}},
            {"paths": {"/x": {"get": {}, "delete": {}}, "/y": {}}},
        ),
        (
            {
                "paths": {
                    "/x": {
                        "post": {
                            "operationId": "before",
                            "deprecated": False,
                            "requestBody": {"required": False},
                            "responses": {"200": {}, "404": {}},
                            "summary": "before",
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "post": {
                            "operationId": "after",
                            "deprecated": True,
                            "requestBody": {"required": True},
                            "responses": {"200": {}, "201": {}},
                            "summary": "after",
                        }
                    }
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "post": {
                            "requestBody": {
                                "content": {"application/json": {"schema": {"type": "string"}}}
                            },
                            "responses": {
                                "200": {"content": {"text/plain": {"schema": {"type": "string"}}}}
                            },
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "post": {
                            "requestBody": {
                                "content": {"application/cbor": {"schema": {"type": "string"}}}
                            },
                            "responses": {
                                "200": {
                                    "content": {"application/json": {"schema": {"type": "string"}}}
                                }
                            },
                        }
                    }
                }
            },
        ),
        (
            {"paths": {"/x": {"get": {"responses": {"4XX": {}}}}}},
            {"paths": {"/x": {"get": {"responses": {"401": {}, "404": {}}}}}},
        ),
        (
            {"servers": [{"url": "/"}], "paths": {}},
            {"servers": [{"url": "/api"}], "paths": {}},
        ),
        (
            {
                "paths": {"/x": {"get": {"security": [{"ApiKey": []}]}}},
            },
            {
                "paths": {"/x": {"get": {"security": [{"ApiKey": []}, {"OAuth": []}]}}},
            },
        ),
        (
            {"paths": {"/x": {"get": {}}}},
            {"paths": {"/x": {"get": {"security": [{"ApiKey": []}]}}}},
        ),
        (
            {
                "components": {
                    "securitySchemes": {
                        "ApiKey": {
                            "type": "apiKey",
                            "name": "X-Key",
                            "in": "header",
                            "flows": {
                                "implicit": {
                                    "authorizationUrl": "https://old.example/auth",
                                    "scopes": {"read": "Read"},
                                }
                            },
                        },
                        "Legacy": {"type": "http", "scheme": "basic"},
                    }
                },
                "paths": {},
            },
            {
                "components": {
                    "securitySchemes": {
                        "ApiKey": {
                            "type": "apiKey",
                            "name": "Authorization",
                            "in": "header",
                            "flows": {
                                "implicit": {
                                    "authorizationUrl": "https://new.example/auth",
                                    "scopes": {"read": "Read"},
                                }
                            },
                        },
                        "Bearer": {"type": "http", "scheme": "bearer"},
                    }
                },
                "paths": {},
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "get": {
                            "security": [{"ApiKey": []}, {"OAuth": []}],
                        }
                    }
                }
            },
            {"paths": {"/x": {"get": {"security": [{"ApiKey": []}]}}}},
        ),
        (
            {"paths": {"/x": {"get": {"security": [{"ApiKey": []}]}}}},
            {"paths": {"/x": {"get": {"security": []}}}},
        ),
        (
            {
                "paths": {
                    "/x": {
                        "get": {
                            "parameters": [
                                {"name": "q", "in": "query", "required": False},
                                {"name": "old", "in": "header", "required": True},
                            ]
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "get": {
                            "parameters": [
                                {"name": "q", "in": "query", "required": True},
                                {"name": "cookie", "in": "cookie", "required": False},
                                {"name": "id", "in": "path", "required": True},
                            ]
                        }
                    }
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {"get": {"parameters": [{"name": "q", "in": "query", "required": True}]}}
                }
            },
            {
                "paths": {
                    "/x": {"get": {"parameters": [{"name": "q", "in": "query", "required": False}]}}
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "post": {
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "optional": {"type": "string"},
                                                "removed": {"type": "boolean"},
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "post": {
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id", "optional", "added"],
                                            "properties": {
                                                "id": {"type": "string"},
                                                "optional": {"type": "string"},
                                                "added": {"type": "string"},
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "required": ["name"],
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "legacy": {"type": "integer"},
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "required": ["name", "added"],
                                                "properties": {
                                                    "name": {"type": "integer"},
                                                    "added": {"type": "boolean"},
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "array",
                                                "items": {"type": "integer"},
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        ),
        (
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {"application/json": {"schema": {"type": "string"}}}
                                }
                            }
                        }
                    }
                }
            },
            {
                "paths": {
                    "/x": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {"schema": {"description": "opaque"}}
                                    }
                                }
                            }
                        }
                    }
                }
            },
        ),
        (
            {"paths": {"/x": {"get": {"summary": "", "description": None}}}},
            {"paths": {"/x": {"get": {"summary": None, "description": ""}}}},
        ),
    ],
)
def test_rust_surface_diff_matches_python_for_implemented_change_classes(old, new):
    assert _rust_surface_diff(old, new) == diff_contracts(old, new).as_dict()


@pytest.mark.parametrize(
    ("is_request", "old_schema", "new_schema"),
    [
        (True, {"type": "string"}, {"type": "string", "maxLength": 8}),
        (
            True,
            {"type": "string", "maxLength": 8},
            {"type": "string", "maxLength": 8.0},
        ),
        (
            True,
            {"type": "string", "maxLength": 20},
            {"type": "string", "maxLength": 8},
        ),
        (
            True,
            {"type": "string", "maxLength": 9007199254740993},
            {"type": "string", "maxLength": 9007199254740992.0},
        ),
        (True, {"type": "string"}, {"type": "string", "pattern": "^[0-9]+$"}),
        (
            True,
            {"type": "string"},
            {"type": "string", "enum": ["red", "blue"]},
        ),
        (True, {"type": "integer"}, {"type": "integer", "enum": [10, 2]}),
        (
            True,
            {"type": "string", "enum": ["blue", "red"]},
            {"type": "string", "enum": ["blue", "green"]},
        ),
        (True, {"type": "integer", "enum": [1]}, {"type": "integer", "enum": [True]}),
        (
            False,
            {"type": "string", "enum": ["blue", "red"]},
            {"type": "string", "enum": ["blue"]},
        ),
        (True, {"type": "string"}, {"type": "string", "format": "uuid"}),
        (
            False,
            {"type": "string", "default": "before"},
            {"type": "string", "default": "after"},
        ),
        (False, {"type": "number", "default": 1}, {"type": "number", "default": 1.0}),
        (
            True,
            {"type": "object"},
            {"type": "object", "additionalProperties": {"type": "integer"}},
        ),
        (
            True,
            {"type": "object", "additionalProperties": {"minimum": 1}},
            {"type": "object", "additionalProperties": {"minimum": 1.0}},
        ),
        (
            False,
            {"type": "object", "additionalProperties": True},
            {"type": "object", "additionalProperties": False},
        ),
    ],
)
def test_rust_inline_schema_keywords_match_python(is_request, old_schema, new_schema):
    def document(schema):
        if is_request:
            operation = {
                "post": {"requestBody": {"content": {"application/json": {"schema": schema}}}}
            }
        else:
            operation = {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": schema}}}}}
            }
        return {"paths": {"/schema": operation}}

    old = document(old_schema)
    new = document(new_schema)
    assert _rust_surface_diff(old, new) == diff_contracts(old, new).as_dict()


@pytest.mark.parametrize(
    ("old_components", "new_components", "old_schema", "new_schema"),
    [
        (
            {"Payload": {"type": "string", "maxLength": 20}},
            {"Payload": {"type": "string", "maxLength": 8}},
            {"$ref": "#/components/schemas/Payload"},
            {"$ref": "#/components/schemas/Payload"},
        ),
        (
            {
                "Payload": {"$ref": "#/components/schemas/Shared"},
                "Shared": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
            {
                "Payload": {"$ref": "#/components/schemas/Shared"},
                "Shared": {"type": "object", "properties": {"id": {"type": "integer"}}},
            },
            {"$ref": "#/components/schemas/Payload"},
            {"$ref": "#/components/schemas/Payload"},
        ),
        (
            {
                "Payload": {
                    "type": "object",
                    "properties": {"id": {"$ref": "#/components/schemas/Item"}},
                },
                "Item": {"type": "string"},
            },
            {
                "Payload": {
                    "type": "object",
                    "properties": {"id": {"$ref": "#/components/schemas/Item"}},
                },
                "Item": {"type": "integer"},
            },
            {"$ref": "#/components/schemas/Payload"},
            {"$ref": "#/components/schemas/Payload"},
        ),
        (
            {
                "Payload": {
                    "type": "object",
                    "properties": {
                        "next": {"$ref": "#/components/schemas/Payload"},
                        "value": {"type": "string"},
                    },
                }
            },
            {
                "Payload": {
                    "type": "object",
                    "properties": {
                        "next": {"$ref": "#/components/schemas/Payload"},
                        "value": {"type": "integer"},
                    },
                }
            },
            {"$ref": "#/components/schemas/Payload"},
            {"$ref": "#/components/schemas/Payload"},
        ),
        (
            {},
            {},
            {"$ref": "#/components/schemas/Missing"},
            {"type": "string"},
        ),
        (
            {"Payload": {"type": "string"}},
            {"Payload": {"type": "string"}},
            {"$ref": "#/components/schemas/Payload", "type": "integer"},
            {"$ref": "#/components/schemas/Payload"},
        ),
    ],
)
def test_rust_schema_reference_comparison_matches_python(
    old_components, new_components, old_schema, new_schema
):
    def document(components, schema):
        return {
            "components": {"schemas": components},
            "paths": {
                "/schema": {
                    "post": {"requestBody": {"content": {"application/json": {"schema": schema}}}}
                }
            },
        }

    old = document(old_components, old_schema)
    new = document(new_components, new_schema)
    assert _rust_surface_diff(old, new) == diff_contracts(old, new).as_dict()
