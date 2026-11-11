"""Differential tests for Rust registered fixture collection and sampling."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.adapters.massive import MassiveAdapter
from agentrouter.evaluation.base import SkippedExternal
from agentrouter.evaluation.registry import dataset_names
from agentrouter.evaluation.runner import _collect

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust_collect(names, *, limit=None, seed=0, source="fixture", massive_languages=None):
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_collect_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "project_root": str(ROOT),
                "names": names,
                "limit": limit,
                "seed": seed,
                "source": source,
                "massive_languages": massive_languages,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize("limit,seed", [(None, 0), (4, 3), (0, 91), (500, -22)])
def test_rust_registered_fixture_collection_matches_python(limit, seed):
    expected_cases, expected_datasets = _collect(dataset_names(), limit, seed, "fixture")
    actual = _rust_collect(dataset_names(), limit=limit, seed=seed)
    assert actual["cases"] == [case.model_dump(mode="json") for case in expected_cases]
    assert actual["datasets"] == expected_datasets


@pytest.mark.parametrize(
    "source,languages",
    [("fixture", None), ("real", None), ("fixture", ["fr", "en"]), ("real", ["xx"])],
)
def test_rust_massive_registered_collection_matches_python(source, languages, monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    if languages is None:
        expected_cases, expected_datasets = _collect(["massive"], 3, 5, source)
    else:
        adapter = MassiveAdapter(languages=languages)
        try:
            sampled = adapter.sample(limit=3, seed=5, source=source)
            expected_cases = sampled
            expected_datasets = {
                "massive": {"status": adapter.availability().value, "n": len(sampled)}
            }
        except SkippedExternal as error:
            expected_cases = []
            expected_datasets = {
                "massive": {"status": "SKIPPED_EXTERNAL", "n": 0, "blocker": str(error)}
            }
    actual = _rust_collect(["massive"], limit=3, seed=5, source=source, massive_languages=languages)
    assert actual["cases"] == [case.model_dump(mode="json") for case in expected_cases]
    assert actual["datasets"] == expected_datasets


def test_rust_real_collection_reports_blockers_without_fixture_fallback(monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    expected_cases, expected_datasets = _collect(dataset_names(), 3, 5, "real")
    actual = _rust_collect(dataset_names(), limit=3, seed=5, source="real")
    assert actual["cases"] == [case.model_dump(mode="json") for case in expected_cases]
    assert actual["datasets"] == expected_datasets
