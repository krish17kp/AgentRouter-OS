"""The runbooks must not make claims that stop being true (TASK-018C).

`docs/RUNBOOKS.md` labels each procedure **Verified**, **Local procedure** or
**Hypothetical**, and the verified ones name the test that backs them. That is
only worth anything if the citation resolves — a runbook claiming verification
it does not have is worse than a runbook with no claim at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RUNBOOKS = Path(__file__).resolve().parents[1] / "docs" / "RUNBOOKS.md"


@pytest.fixture(scope="module")
def text() -> str:
    return RUNBOOKS.read_text(encoding="utf-8")


def test_every_cited_test_file_exists(text):
    repo = RUNBOOKS.parents[1]
    cited = set(re.findall(r"(tests/[a-z0-9_]+\.py)", text))
    assert cited, "the runbooks cite no tests at all"
    missing = sorted(name for name in cited if not (repo / name).exists())
    assert missing == [], f"runbooks cite files that do not exist: {missing}"


def test_every_cited_test_function_exists(text):
    """Names the runbooks give as evidence must be real test functions."""
    repo = RUNBOOKS.parents[1]
    cited = set(re.findall(r"::(test_[a-z0-9_]+)", text))
    assert cited, "no verified procedure cites a test"

    defined: set[str] = set()
    for path in (repo / "tests").glob("test_*.py"):
        defined.update(
            re.findall(r"^def (test_[a-z0-9_]+)", path.read_text(encoding="utf-8"), re.M)
        )

    missing = sorted(name for name in cited if name not in defined)
    assert missing == [], f"runbooks cite tests that do not exist: {missing}"


def test_every_procedure_declares_how_far_it_is_proven(text):
    """An unlabelled procedure invites the reader to assume it was tested."""
    headings = re.findall(r"^## \d+\. (.+)$", text, re.M)
    assert len(headings) >= 10, headings
    unlabelled = [
        h for h in headings if not re.search(r"\*\*(Verified|Local procedure|Hypothetical)", h)
    ]
    assert unlabelled == [], f"procedures with no evidence label: {unlabelled}"


def test_production_guidance_is_marked_hypothetical(text):
    """This project has no hosted deployment; claiming otherwise would be
    inventing operational experience it does not have."""
    section = text[text.index("## 12.") :]
    assert "Hypothetical" in section.splitlines()[0]
    assert "no hosted deployment" in section
