"""Differential tests for frozen context-band generalization measurement."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation.context_bands import (
    ContextBandCase,
    cross_split_leaks,
    evaluate_generalization,
    prompt_similarity,
    score,
)

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_context_band_generalization_report_matches_python():
    expected = evaluate_generalization()
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_context_bands_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected


def test_rust_context_split_leakage_matches_python_sequence_matcher():
    holdout = [
        ContextBandCase("exact", "A small prompt, with punctuation!", "small", "coding"),
        ContextBandCase("near", "Analyze this production repository for security risks", "large", "audit"),
        ContextBandCase("popular", "z" * 210 + " marker alpha beta", "medium", "review"),
    ]
    references = {
        "first": [
            "a small prompt with punctuation",
            "Analyze this production repository for security risk",
            "z" * 209 + "y marker alpha beta",
        ],
        "second": ["unrelated short text"],
    }
    expected = cross_split_leaks(holdout, references)
    pairs = [
        ("café 🧭 routing", "cafe routing"),
        ("a\u0301 test", "a test"),
        ("ΟΣ routing", "ος ROUTING"),
        ("x" * 210 + " a b", "x" * 209 + "y a b"),
        ("alpha beta gamma", "alpha beta delta"),
        ("", ""),
    ]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_context_leaks_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "holdout": [case.__dict__ for case in holdout],
                "references": references,
                "comparisons": pairs,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout)
    assert actual["leaks"] == expected
    assert actual["similarities"] == [prompt_similarity(*pair) for pair in pairs]


def test_rust_context_band_score_matches_custom_python_predictions():
    cases = [
        ContextBandCase("a", "first prompt", "small", "coding"),
        ContextBandCase("b", "second prompt", "medium", "review"),
        ContextBandCase("c", "third prompt", "large", "analysis"),
        ContextBandCase("d", "fourth prompt", "large", "analysis"),
    ]
    predictions = ["small", "large", "medium", "large"]
    prediction_by_prompt = {
        case.prompt: prediction for case, prediction in zip(cases, predictions, strict=True)
    }
    expected = score(cases, lambda prompt: prediction_by_prompt[prompt])
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_context_score_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"cases": [case.__dict__ for case in cases], "predictions": predictions}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected
