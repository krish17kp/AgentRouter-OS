"""Offline differential checks for provider refresh conversion in Rust."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter import refresh

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(request: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "refresh_from_json",
            "-p",
            "agentrouter-cli",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _dump(entry) -> dict:
    return entry.model_dump(mode="json", exclude_none=True)


def _assert_model_matches(operation: str, raw: dict, expected: dict) -> None:
    process = _rust({"operation": operation, "raw": raw, "today": expected["last_updated"]})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["value"] == expected


OPENROUTER_ROWS = [
    {
        "id": "vendor/frontier-x",
        "name": "Frontier X",
        "context_length": 200000,
        "pricing": {"prompt": "0.00002", "completion": "0.0001"},
        "supported_parameters": ["tools", "temperature"],
        "architecture": {"input_modalities": ["text", "image"]},
        "top_provider": {"max_completion_tokens": 32000},
    },
    {
        "id": "vendor/cheap-y",
        "context_length": 32000,
        "pricing": {"prompt": 0},
        "supported_parameters": [],
        "architecture": {"input_modalities": ["text"]},
    },
    {"id": "vendor/broken-no-context", "pricing": {"prompt": "0.000001"}},
    {
        "id": "vendor/mid-z",
        "context_length": 128000,
        "pricing": {"prompt": "0.000002"},
        "supported_parameters": ["tools"],
        "architecture": {"input_modalities": ["text"]},
    },
]


@pytest.mark.parametrize("raw", OPENROUTER_ROWS[:2] + OPENROUTER_ROWS[3:])
def test_rust_openrouter_mapping_matches_python(raw):
    _assert_model_matches("map_openrouter", raw, _dump(refresh.map_openrouter_model(raw)))


@pytest.mark.parametrize("explicit_max_output", [None, 2**120])
def test_rust_openrouter_mapping_preserves_unbounded_token_counts(explicit_max_output):
    raw = {
        "id": "vendor/huge-context",
        "context_length": 2**100,
        "pricing": {"prompt": 0},
    }
    if explicit_max_output is not None:
        raw["top_provider"] = {"max_completion_tokens": explicit_max_output}
    _assert_model_matches("map_openrouter", raw, _dump(refresh.map_openrouter_model(raw)))


@pytest.mark.parametrize(
    "model_id",
    [
        "gpt-4o-mini-2024-07-18",
        "gpt-4o-2024-08-06",
        "gpt-4.1-nano-2026-01-01",
        "gpt-4.1-mini-2026-01-01",
        "gpt-4.1-2026-01-01",
        "gpt-5-mini-2026-01-01",
        "gpt-5-nano-2026-01-01",
        "gpt-5-2026-01-01",
        "o3-mini-2025-01-01",
        "o3-2025-01-01",
        "o4-mini-2025-01-01",
    ],
)
def test_rust_openai_family_mapping_matches_python(model_id):
    raw = {"id": model_id}
    _assert_model_matches("map_openai", raw, _dump(refresh.map_openai_model(raw)))


@pytest.mark.parametrize(
    "price",
    [0.0, 5e-7, 2e-6, 1e-5, 2e-5],
)
def test_rust_openrouter_price_tiers_match_python(price):
    process = _rust({"operation": "pricing_tier", "prompt_price": price})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["value"] == refresh._pricing_tier(price).value


def test_rust_openrouter_payload_limit_filter_and_warnings_match_python(monkeypatch):
    payload = {"data": OPENROUTER_ROWS}
    monkeypatch.setattr(refresh, "_http_get_json", lambda *_args: payload)
    python_entries, python_warnings = refresh.fetch_openrouter_models(None, limit=25)
    today = python_entries[0].last_updated.isoformat()

    process = _rust(
        {
            "operation": "openrouter_from_payload",
            "raw": payload,
            "limit": 25,
            "today": today,
        }
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)["value"]
    assert actual == {
        "entries": [_dump(entry) for entry in python_entries],
        "warnings": python_warnings,
    }

    matched = _rust(
        {
            "operation": "openrouter_from_payload",
            "raw": payload,
            "limit": 1,
            "match": "mid-",
            "today": today,
        }
    )
    assert matched.returncode == 0, matched.stderr
    assert [row["model_id"] for row in json.loads(matched.stdout)["value"]["entries"]] == [
        "vendor/mid-z"
    ]


def test_rust_openai_payload_skips_unknown_families_like_python(monkeypatch):
    payload = {
        "data": [
            {"id": "gpt-4.1-mini-2026-01-01"},
            {"id": "text-embedding-3-small"},
        ]
    }
    monkeypatch.setattr(refresh, "_http_get_json", lambda *_args: payload)
    python_entries, python_warnings = refresh.fetch_openai_models("test-key", limit=10)
    today = python_entries[0].last_updated.isoformat()
    process = _rust(
        {
            "operation": "openai_from_payload",
            "raw": payload,
            "limit": 10,
            "today": today,
        }
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)["value"]
    assert actual == {
        "entries": [_dump(entry) for entry in python_entries],
        "warnings": python_warnings,
    }
    assert [row["model_id"] for row in actual["entries"]] == ["gpt-4.1-mini-2026-01-01"]
    assert actual["warnings"] == [
        "skipped 1 catalog entries with no family mapping (non-chat or unknown)"
    ]
