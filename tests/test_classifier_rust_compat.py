"""Python/Rust classifier compatibility check for the R2 milestone.

Runs the same prompts through `agentrouter.classifier.classify()` (Python,
release-gate authority) and the Rust `agentrouter-classifier` port (via the
`classify_cli` bin) and asserts the full `Classification` dict matches
field-for-field. The prompt set is drawn directly from the existing
regression suites (`test_classifier_regression.py`, `test_mvp.py`,
`test_confidence.py`) since those are the fixtures that already encode the
classifier's documented precedence rules and known-tricky cases.

Skips (does not fail) when `cargo` isn't on PATH, matching
`test_rust_compat.py`'s convention from the R1 milestone.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from agentrouter.classifier import classify
from agentrouter.schema import Level

RUST_CRATE_DIR = "rust/agentrouter-classifier"
ROOT = Path(__file__).resolve().parents[1]
GOLD_CASES = yaml.safe_load(
    (ROOT / "agentrouter" / "benchmarks" / "classifier_gold_v1.yaml").read_text(encoding="utf-8")
)["cases"]

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")

PROMPTS = [
    "Refactor the payment module and add unit tests",
    "build a mvp for a sales guide app",
    "build a rag system which identifies the pdf very well and stores properly with chunking",
    "write a sales guide for the sales team",
    "build a sales guide app",
    "Rewrite this paragraph to be more concise",
    "Draft a professional email declining a meeting request",
    "Decide between PostgreSQL and MongoDB for our new service",
    "Write a blog post about our new API launch",
    "Implement a document ingestion pipeline with embeddings",
    "Build a vector database search over our knowledge base",
    "Write a PDF parser that extracts tables and text",
    "Add input validation to the signup form",
    "Add a dark mode toggle to the settings page",
    "Train a classifier to detect spam messages",
    "Fix the SQL injection vulnerability in the search endpoint",
    "Configure OAuth2 login with Google",
    "Encrypt the PII fields in the user database",
    "Rotate the production database credentials",
    "Deploy the new version to the Kubernetes cluster",
    "Implement the payment processing with Stripe",
    "Run the terraform apply to provision the infrastructure",
    "Store user passwords securely with hashing and salting",
    "Fix the memory leak in the image processing worker",
    "Implement a binary search function in Python",
    "Write a regex that matches valid email addresses",
    "Optimize this SQL query that is running slowly",
    "make a plan",
    "Add docstrings to the functions in utils.py",
    "write a bash one-liner to count lines in a file",
    "Refactor our auth module to use JWT rotation and add tests",
    "Summarize this 300k-token filing into 10 bullets",
    "Describe what's wrong in this UI screenshot",
    "Build a Python Typer CLI command",
    "Refactor authentication routes and migrate JWT token handling in production",
    "Summarize a 300k-token repository and generate an architecture report",
    "refactor the payment module and add unit tests",
    "do it",
    "summarize and refactor this",
    "summarize the repo and refactor the auth module",
]


def _rust_classification_json(task: str) -> dict:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "classify_cli", "--", task],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout.strip())


@pytest.mark.parametrize("prompt", PROMPTS)
def test_classification_matches_between_python_and_rust(prompt):
    python_json = json.loads(classify(prompt).model_dump_json())
    rust_json = _rust_classification_json(prompt)
    assert rust_json == python_json, f"mismatch for prompt: {prompt!r}"


@pytest.mark.parametrize("case", GOLD_CASES, ids=[case["id"] for case in GOLD_CASES])
def test_gold_classifier_parity(case):
    prompt = case["prompt"]
    assert _rust_classification_json(prompt) == classify(prompt).model_dump(mode="json")


def test_classifier_explicit_overrides_match_python():
    task = "Review this repository for security issues"
    overrides = {
        "context_tokens": 123_000,
        "risk": "medium",
        "tools": ["web", "vision"],
        "uncertainty_threshold": 0.9,
    }
    expected = classify(
        task,
        context_tokens=overrides["context_tokens"],
        risk=Level.medium,
        tools=overrides["tools"],
        uncertainty_threshold=overrides["uncertainty_threshold"],
    )
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-classifier", "--bin", "classify_from_json"],
        cwd=ROOT,
        input=json.dumps({"task": task, "overrides": overrides}),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(completed.stdout) == expected.model_dump(mode="json")


@pytest.mark.parametrize("input_payload", [{"task": ""}, {"task": "hi", "overrides": {"extra": 1}}])
def test_classifier_json_rejects_invalid_request(input_payload):
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-classifier", "--bin", "classify_from_json"],
        cwd=ROOT,
        input=json.dumps(input_payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
