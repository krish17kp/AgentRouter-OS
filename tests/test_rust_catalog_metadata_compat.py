"""Python/Rust differential checks for catalog metadata operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from agentrouter.catalog_ops import (
    deprecations,
    list_generated,
    read_provenance,
    read_status,
)
from agentrouter.catalog_ops import (
    restore as restore_python,
)
from agentrouter.catalog_ops import (
    rollback as rollback_python,
)

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
        "path": str(expected.path),
        "count": expected.count,
        "newest": expected.newest.isoformat() if expected.newest else None,
        "age_days": expected.age_days,
        "stale": expected.stale,
        "source_url": expected.source_url,
        "fetched_at": expected.fetched_at,
        "tool_version": expected.tool_version,
        "summary": expected.summary,
    }


def test_rust_catalog_list_generated_matches_python_order_and_summary(tmp_path):
    (tmp_path / "models.zeta.generated.yaml").write_text("models: []\n", encoding="utf-8")
    (tmp_path / "models.alpha.generated.yaml").write_text(
        "models:\n  - id: a\n    last_updated: '2026-11-12'\n"
        "provenance:\n  source_url: 'https://example.test/a'\n",
        encoding="utf-8",
    )
    expected = list_generated(tmp_path, today=date(2026, 11, 12))
    process = _rust(
        {
            "operation": "list_generated",
            "reg_dir": str(tmp_path),
            "today": "2026-11-12",
        }
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)["value"]
    assert [status["provider"] for status in actual] == [status.provider for status in expected]
    assert [status["summary"] for status in actual] == [status.summary for status in expected]


def test_rust_catalog_rollback_and_restore_match_python(tmp_path):
    python_dir = tmp_path / "python"
    rust_dir = tmp_path / "rust"
    python_dir.mkdir()
    rust_dir.mkdir()
    filename = "models.openai.generated.yaml"
    original = b"models: [raw bytes]\n"
    (python_dir / filename).write_bytes(original)
    (rust_dir / filename).write_bytes(original)

    expected_backup = rollback_python(python_dir, "openai")
    process = _rust({"operation": "rollback", "reg_dir": str(rust_dir), "provider": "openai"})
    assert process.returncode == 0, process.stderr
    actual_backup = json.loads(process.stdout)["value"]
    assert expected_backup is not None
    assert Path(actual_backup).name == expected_backup.name
    assert Path(actual_backup).read_bytes() == expected_backup.read_bytes() == original
    assert not (rust_dir / filename).exists()

    expected_path = restore_python(python_dir, "openai")
    process = _rust({"operation": "restore", "reg_dir": str(rust_dir), "provider": "openai"})
    assert process.returncode == 0, process.stderr
    assert Path(json.loads(process.stdout)["value"]).name == expected_path.name
    assert (rust_dir / filename).read_bytes() == (python_dir / filename).read_bytes() == original


def test_rust_catalog_rollback_and_restore_missing_are_noops(tmp_path):
    for operation in ("rollback", "restore"):
        process = _rust({"operation": operation, "reg_dir": str(tmp_path), "provider": "openai"})
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout)["value"] is None


def test_rust_catalog_restore_refuses_to_replace_a_refreshed_file(tmp_path):
    rust_dir = tmp_path / "rust"
    rust_dir.mkdir()
    filename = "models.openai.generated.yaml"
    (rust_dir / filename).write_text("refreshed", encoding="utf-8")
    (rust_dir / f"{filename}.bak").write_text("backup", encoding="utf-8")
    process = _rust({"operation": "restore", "reg_dir": str(rust_dir), "provider": "openai"})
    assert process.returncode != 0
    assert (rust_dir / filename).read_text(encoding="utf-8") == "refreshed"
    assert (rust_dir / f"{filename}.bak").read_text(encoding="utf-8") == "backup"


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks requires Windows runner privileges")
def test_rust_catalog_restore_refuses_symlink_backup(tmp_path):
    rust_dir = tmp_path / "rust"
    rust_dir.mkdir()
    filename = "models.openai.generated.yaml"
    outside = tmp_path / "outside.yaml"
    outside.write_text("outside", encoding="utf-8")
    (rust_dir / f"{filename}.bak").symlink_to(outside)
    process = _rust({"operation": "restore", "reg_dir": str(rust_dir), "provider": "openai"})
    assert process.returncode != 0
    assert outside.read_text(encoding="utf-8") == "outside"
    assert not (rust_dir / filename).exists()
