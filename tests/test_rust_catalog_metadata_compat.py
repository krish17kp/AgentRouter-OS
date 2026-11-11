"""Python/Rust differential checks for catalog metadata operations."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from agentrouter.catalog_ops import deprecations, read_provenance, read_status

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(request):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "catalog_ops_from_json",
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


def test_rust_catalog_deprecations_match_python():
    previous = {"zeta", "removed-b", "alpha", "removed-a"}
    current = {"zeta", "new"}
    process = _rust(
        {
            "operation": "deprecations",
            "previous": list(previous),
            "current": list(current),
        }
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["value"] == deprecations(previous, current)


def test_rust_catalog_provenance_is_best_effort_like_python(tmp_path):
    path = tmp_path / "models.openai.generated.yaml"
    path.write_text(
        'models: []\nprovenance: {source_url: "https://example.test/catalog"}\n',
        encoding="utf-8",
    )
    assert _rust_provenance(path) == read_provenance(path)

    for content in ("models: []\n", "provenance: [not, a, mapping]\n", "provenance: [\n"):
        path.write_text(content, encoding="utf-8")
        assert _rust_provenance(path) == read_provenance(path)


def _rust_provenance(path):
    process = _rust({"operation": "read_provenance", "path": str(path)})
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)["value"]


def test_rust_catalog_status_preserves_freshness_and_provenance_fields(tmp_path):
    path = tmp_path / "models.openai.generated.yaml"
    path.write_text(
        "models:\n  - id: model-a\n    last_updated: '2026-11-11'\n"
        "provenance:\n  source_url: 'https://example.test/catalog'\n"
        "  fetched_at: '2026-11-12T00:00:00Z'\n  tool_version: '0.5.0rc1'\n",
        encoding="utf-8",
    )
    expected = read_status(path, today=date(2026, 11, 12))
    process = _rust({"operation": "read_status", "path": str(path), "today": "2026-11-12"})
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)["value"]
    assert actual == {
        "provider": expected.provider,
        "path": expected.path.as_posix(),
        "count": expected.count,
        "newest": expected.newest.isoformat() if expected.newest else None,
        "age_days": expected.age_days,
        "stale": expected.stale,
        "source_url": expected.source_url,
        "fetched_at": expected.fetched_at,
        "tool_version": expected.tool_version,
    }
