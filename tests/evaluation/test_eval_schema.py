"""Tests for the normalized evaluation-case schema."""

import pytest
from pydantic import ValidationError

from agentrouter.evaluation.schema import (
    EvaluationCase,
    ExpectedClassification,
    normalized_hash,
)


def test_normalized_hash_ignores_case_and_punctuation():
    assert normalized_hash("Build a RAG system!") == normalized_hash("build a  rag system")


def test_normalized_hash_differs_for_different_tasks():
    assert normalized_hash("write a poem") != normalized_hash("write code")


def test_empty_task_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase(id="x", dataset="d", task="   ")


def test_with_checksum_fills_task_hash():
    case = EvaluationCase(id="x", dataset="d", task="Build a REST API").with_checksum()
    assert case.checksum == case.task_hash
    assert len(case.checksum) == 16


def test_expected_defaults_are_empty_sets():
    e = ExpectedClassification()
    assert e.task_types == [] and e.required_tools == []


def test_acceptable_sets_accept_multiple_labels():
    case = EvaluationCase(
        id="x",
        dataset="d",
        task="build a sales guide app",
        expected=ExpectedClassification(task_types=["coding", "reasoning"]),
    )
    assert len(case.expected.task_types) == 2
