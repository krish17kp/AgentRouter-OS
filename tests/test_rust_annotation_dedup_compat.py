"""Differential checks for annotation duplicate and leakage guards."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation import dedup

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def test_rust_annotation_dedup_matches_python():
    repetitive = "review the complete payment service for security problems " * 5
    prompts = [
        "Fix the bug in the payment module!",
        "fix, the bug in the payment module",
        "Review the payment service for authentication bypass risks",
        "Review payment service for authentication bypass risks",
        "café: protect the user profile",
        "cafe protect the user profile",
        repetitive,
        repetitive + "and report each issue",
    ]
    candidate = [
        "Fix the bug in the payment module.",
        "Review the payment service for authentication bypass risks",
        "An unrelated prompt about a haiku",
    ]
    reference = [
        "fix, the bug in the payment module",
        "Review payment service for authentication bypass risks",
    ]
    threshold = dedup.NEAR_THRESHOLD
    expected = {
        "normalized": [dedup.normalize(prompt) for prompt in prompts],
        "similarities": [
            dedup.similarity(left, right)
            for left, right in zip(prompts, prompts[1:], strict=False)
        ],
        "clusters": dedup.cluster(prompts, threshold),
        "leakage": [
            duplicate.__dict__
            for duplicate in dedup.find_leakage(candidate, reference, threshold)
        ],
    }
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_dedup_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps(
            {
                "prompts": prompts,
                "candidate": candidate,
                "reference": reference,
                "threshold": threshold,
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected
