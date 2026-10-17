"""Live Python/Rust compatibility test for the R2 registry parsing milestone.

The authoritative Python loader and the Rust binary read the same bundled
YAML catalogs and must agree on model ordering, keys, defaults, capability
facts and unresolved-fallback warnings. The Rust CI job installs Cargo so
this test is not silently skipped there.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.registry import load_models, load_providers

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "agentrouter" / "seeds"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def test_registry_seed_contract_matches_python() -> None:
    providers = load_providers(SEEDS / "providers.yaml")
    models, warnings = load_models(SEEDS / "models.yaml", providers)
    expected = {
        "providers": sorted(providers),
        "models": [
            {
                "key": model.key,
                "vendor_key": model.vendor_key,
                "name": model.name,
                "context_window": model.context_window,
                "max_output_tokens": model.max_output_tokens,
                "pricing_tier": model.pricing_tier.value,
                "tool_support": model.tool_support,
                "fallback": model.fallback,
            }
            for model in models
        ],
        "warnings": warnings,
    }
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "-p", "agentrouter-registry", "--bin", "print_registry"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout) == expected
