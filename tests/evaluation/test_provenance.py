"""Tests for provenance + dataset-quality / leakage reporting."""

from agentrouter.evaluation.provenance import dataset_quality, environment_snapshot
from agentrouter.evaluation.schema import (
    AnnotationMethod,
    EvaluationCase,
    ExpectedClassification,
    Provenance,
)


def _case(id, task, group=None, split=None, method=AnnotationMethod.model_assisted):
    return EvaluationCase(
        id=id,
        dataset="d",
        task=task,
        paraphrase_group=group,
        source_split=split,
        expected=ExpectedClassification(task_types=["coding"], risks=["high"]),
        provenance=Provenance(method=method),
    ).with_checksum()


def test_environment_snapshot_has_keys():
    env = environment_snapshot(git_sha="abc123")
    assert env["git_sha"] == "abc123"
    assert "python" in env and "agentrouter_version" in env


def test_quality_counts_cases_and_provenance():
    q = dataset_quality([_case("a", "task one"), _case("b", "task two")])
    assert q["n_cases"] == 2
    assert q["model_assisted_count"] == 2


def test_paraphrase_family_leak_detected_across_splits():
    cases = [
        _case("a", "build a sales app", group="sales", split="dev"),
        _case("b", "create a sales application", group="sales", split="holdout"),
    ]
    q = dataset_quality(cases)
    assert "sales" in q["leaked_paraphrase_families"]


def test_no_leak_when_family_in_one_split():
    cases = [
        _case("a", "build a sales app", group="sales", split="dev"),
        _case("b", "create a sales application", group="sales", split="dev"),
    ]
    q = dataset_quality(cases)
    assert q["leaked_paraphrase_families"] == []
