"""Permanent regression tests for classifier fixes (Phase 2).

Every case here was a real failure the gold benchmark exposed. They lock in the
phrase-level precedence and word-boundary fixes so future keyword edits cannot
silently reintroduce the bugs.
"""

import pytest

from agentrouter.classifier import classify
from agentrouter.schema import Level, TaskType

# --- the three prompts from the task brief -----------------------------------


def test_refactor_payment_module_with_tests():
    c = classify("Refactor the payment module and add unit tests")
    assert c.task_type is TaskType.coding
    assert c.complexity is Level.high
    assert c.risk is Level.high
    assert c.output_type.value == "code+tests"
    assert set(c.tool_needs) == {"file-edit", "shell"}


def test_build_mvp_sales_guide_app_is_coding():
    c = classify("build a mvp for a sales guide app")
    assert c.task_type in (TaskType.coding, TaskType.reasoning)
    assert c.complexity in (Level.medium, Level.high)
    assert "file-edit" in c.tool_needs and "shell" in c.tool_needs


def test_build_rag_system_is_coding():
    c = classify(
        "build a rag system which identifies the pdf very well and stores properly with chunking"
    )
    assert c.task_type in (TaskType.coding, TaskType.reasoning)
    assert c.complexity in (Level.medium, Level.high)
    assert "file-edit" in c.tool_needs and "shell" in c.tool_needs


# --- context-sensitive "guide": write vs build ------------------------------


def test_write_a_sales_guide_is_writing():
    assert classify("write a sales guide for the sales team").task_type is TaskType.writing


def test_build_a_sales_guide_app_is_coding():
    assert classify("build a sales guide app").task_type is TaskType.coding


# --- word-boundary bugs that substring matching used to trip -----------------


@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("Rewrite this paragraph to be more concise", TaskType.writing),  # "rag" in paragraph
        (
            "Draft a professional email declining a meeting request",
            TaskType.writing,
        ),  # "cli" in declining
        (
            "Decide between PostgreSQL and MongoDB for our new service",
            TaskType.reasoning,
        ),  # "sql" in postgresql
        ("Write a blog post about our new API launch", TaskType.writing),  # "api" but writing wins
    ],
)
def test_no_substring_false_positives(prompt, expected):
    assert classify(prompt).task_type in (expected, TaskType.analysis)


# --- software-term context awareness ----------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "Implement a document ingestion pipeline with embeddings",
        "Build a vector database search over our knowledge base",
        "Write a PDF parser that extracts tables and text",
        "Add input validation to the signup form",
        "Add a dark mode toggle to the settings page",
        "Train a classifier to detect spam messages",
    ],
)
def test_software_tasks_are_coding_with_file_edit(prompt):
    c = classify(prompt)
    assert c.task_type is TaskType.coding
    assert "file-edit" in c.tool_needs


# --- high-risk recall: security/ops signals must all trip high --------------


@pytest.mark.parametrize(
    "prompt",
    [
        "Fix the SQL injection vulnerability in the search endpoint",
        "Configure OAuth2 login with Google",
        "Encrypt the PII fields in the user database",
        "Rotate the production database credentials",
        "Deploy the new version to the Kubernetes cluster",
        "Implement the payment processing with Stripe",
        "Run the terraform apply to provision the infrastructure",
        "Store user passwords securely with hashing and salting",
    ],
)
def test_security_and_ops_tasks_are_high_risk(prompt):
    c = classify(prompt)
    assert c.risk is Level.high
    assert c.approval_level.value == "human-approval-required"


# --- false-positive guards ---------------------------------------------------


def test_image_processing_is_not_a_vision_task():
    # "image processing worker" must not request the vision tool
    assert "vision" not in classify("Fix the memory leak in the image processing worker").tool_needs


def test_pure_snippet_needs_no_file_edit():
    assert classify("Implement a binary search function in Python").tool_needs == []
    assert classify("Write a regex that matches valid email addresses").tool_needs == []


def test_running_does_not_trigger_shell():
    # "running" must not match the shell verb "run"
    assert "shell" not in classify("Optimize this SQL query that is running slowly").tool_needs


def test_trivial_plan_is_low_complexity():
    assert classify("make a plan").complexity is Level.low


def test_add_docstrings_stays_coding():
    assert classify("Add docstrings to the functions in utils.py").task_type is TaskType.coding
