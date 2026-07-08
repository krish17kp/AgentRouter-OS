"""PromptGenerator — tool-tailored execution prompt (templated, never model-hardcoded)."""

from __future__ import annotations

from .schema import Classification

_TEMPLATE = """# Execution Prompt

Target tool: {tool}

## Task
{task}

## Context for the executing tool
- Task type: {task_type} | Complexity: {complexity} | Risk: {risk}
- Expected output: {output_type}
- Estimated context: ~{context_tokens} tokens ({context_band})
- Tools you may need: {tools}

## Instructions
1. Restate the task in your own words before starting.
2. Produce the expected output type ({output_type}).
3. Keep changes minimal and within the stated scope.
{risk_line}

## Safety checklist (complete before applying results)
{checklist}
"""


def generate_prompt(task: str, tool_key: str, cls: Classification, checklist: list[str]) -> str:
    risk_line = (
        "4. STOP before any irreversible action - this task requires human approval."
        if cls.approval_level.value == "human-approval-required"
        else "4. Flag anything unexpected instead of guessing."
    )
    return _TEMPLATE.format(
        tool=tool_key,
        task=task,
        task_type=cls.task_type.value,
        complexity=cls.complexity.value,
        risk=cls.risk.value,
        output_type=cls.output_type.value,
        context_tokens=cls.context_tokens,
        context_band=cls.context_band.value,
        tools=", ".join(cls.tool_needs) or "none",
        risk_line=risk_line,
        checklist="\n".join(f"- [ ] {item}" for item in checklist),
    )
