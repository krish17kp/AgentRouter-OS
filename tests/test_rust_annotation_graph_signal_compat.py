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


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "not an object",
        12,
        {"nodes": 3},
        {"nodes": [], "edges": 5},
        {"nodes": [], "links": True},
    ],
)
def test_rust_graph_signal_rejects_malformed_iterable_shapes_like_python(tmp_path, raw):
    graph = tmp_path / "malformed.json"
    graph.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises((AttributeError, TypeError)):
        impact_for("inspect classifier", graph)
    result = _rust("inspect classifier", graph)
    assert result.returncode != 0


def test_rust_graph_signal_matches_python_mapping_node_iteration(tmp_path):
    graph = tmp_path / "mapping-nodes.json"
    graph.write_text(json.dumps({"nodes": {"bad": "ignored key"}}), encoding="utf-8")
    _assert_parity("inspect classifier", graph)


def test_rust_graph_signal_matches_four_entry_python_lru_cache(tmp_path):
    paths = [tmp_path / f"cache-{index}.json" for index in range(5)]
    sequence = [
        {
            "prompt": "inspect alpha",
            "graph_path": str(paths[0]),
            "write_graph": {"nodes": [{"id": "alpha"}]},
        },
        {
            "prompt": "inspect alpha",
            "graph_path": str(paths[0]),
            "write_graph": {"nodes": [{"id": "zeta"}]},
        },
    ]
    sequence.extend(
        {
            "prompt": f"inspect node{index}",
            "graph_path": str(paths[index]),
            "write_graph": {"nodes": [{"id": f"node{index}"}]},
        }
        for index in range(1, 5)
    )
    sequence.extend(
        [
            {
                "prompt": "inspect alpha",
                "graph_path": str(paths[0]),
                "write_graph": {"nodes": [{"id": "zeta"}]},
            },
            {"prompt": "inspect missing", "graph_path": str(tmp_path / "missing-cache.json")},
            {
                "prompt": "inspect missing",
                "graph_path": str(tmp_path / "missing-cache.json"),
                "write_graph": {"nodes": [{"id": "missing"}]},
            },
        ]
    )

    expected = []
    for entry in sequence:
        if "write_graph" in entry:
            Path(entry["graph_path"]).write_text(json.dumps(entry["write_graph"]), encoding="utf-8")
        signal = impact_for(entry["prompt"], entry["graph_path"])
        expected.append(
            {
                "available": signal.available,
                "matched_nodes": signal.matched_nodes,
                "dependency_reach": signal.dependency_reach,
                "feature": signal.feature,
            }
        )

    Path(sequence[-1]["graph_path"]).unlink()

    process = subprocess.run(
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
        input=json.dumps({"sequence": sequence}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=True,
    )
    assert json.loads(process.stdout) == expected
