"""Python/Rust differential checks for the optional repository graph signal."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.annotation.graph_signals import impact_for

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(prompt: str, graph_path: Path):
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_annotation_graph_signal_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"prompt": prompt, "graph_path": str(graph_path)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _assert_parity(prompt: str, path: Path):
    expected = impact_for(prompt, graph_path=path)
    result = _rust(prompt, path)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual == {
        "available": expected.available,
        "matched_nodes": expected.matched_nodes,
        "dependency_reach": expected.dependency_reach,
        "feature": expected.feature,
    }


def test_rust_graph_signal_matches_absent_and_invalid_graph_fallbacks(tmp_path):
    _assert_parity("refactor the parser", tmp_path / "missing.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{bad json", encoding="utf-8")
    _assert_parity("refactor the parser", invalid)


def test_rust_graph_signal_matches_node_names_edges_and_saturation(tmp_path):
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "classifier"},
                    {"name": "src/Engine.rs"},
                    {"label": "Host Manager"},
                    {"file": "src/registry/models.py"},
                    None,
                ],
                "edges": [
                    {"source": "classifier", "target": "engine"},
                    {"source": "classifier", "target": "engine"},
                    {"source": "classifier", "target": "registry"},
                    {"source": 7, "target": "ignored"},
                ],
            }
        ),
        encoding="utf-8",
    )
    _assert_parity("Audit CLASSIFIER and src/registry; engine", graph)
    _assert_parity("write a limerick", graph)
    _assert_parity("x y z", graph)


def test_rust_graph_signal_uses_links_when_edges_are_empty(tmp_path):
    graph = tmp_path / "links.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [{"id": "server"}],
                "edges": [],
                "links": [{"source": "server", "target": "api"}],
            }
        ),
        encoding="utf-8",
    )
    _assert_parity("Inspect server", graph)
    empty_edges = tmp_path / "falsey-edges.json"
    empty_edges.write_text(
        json.dumps(
            {
                "nodes": [{"id": "server"}],
                "edges": "",
                "links": [{"source": "server", "target": "api"}],
            }
        ),
        encoding="utf-8",
    )
    _assert_parity("Inspect server", empty_edges)


def test_rust_graph_signal_saturates_at_one(tmp_path):
    graph = tmp_path / "wide-graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [{"id": "classifier"}],
                "edges": [{"source": "classifier", "target": f"neighbor-{i}"} for i in range(24)],
            }
        ),
        encoding="utf-8",
    )
    _assert_parity("audit classifier", graph)
