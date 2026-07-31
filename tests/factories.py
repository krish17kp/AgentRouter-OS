"""Minimal in-memory builders for mutation-hardening unit tests.

These construct real schema objects (no YAML/registry round-trip) so tests can
pin the exact behavior of pure functions in hosts.py / controls.py / safety.py.
"""

from __future__ import annotations

from agentrouter.schema import (
    Ability,
    ApprovalLevel,
    Classification,
    ContextBand,
    DeprecationStatus,
    ExecutionMode,
    ExecutionTarget,
    LatencyTier,
    Level,
    ModelEntry,
    OutputType,
    PricingTier,
    ReleaseChannel,
    SnapshotType,
    TaskType,
)


def make_target(
    host: str = "claude-code",
    *,
    host_model_id: str = "claude-x",
    execution_mode: ExecutionMode = ExecutionMode.cli,
    command_template: list[str] | None = None,
    required_command: str | None = None,
    required_env: list[str] | None = None,
) -> ExecutionTarget:
    return ExecutionTarget(
        host=host,
        host_model_id=host_model_id,
        execution_mode=execution_mode,
        command_template=command_template,
        required_command=required_command,
        required_env=required_env or [],
    )


def make_model(
    *,
    provider: str = "anthropic",
    vendor: str | None = None,
    model_id: str = "claude-x",
    display_name: str | None = "Claude X",
    release_channel: ReleaseChannel = ReleaseChannel.stable,
    pricing_tier: PricingTier = PricingTier.medium,
    input_price_per_million: float | None = None,
    tool_support: list[str] | None = None,
    context_window: int = 200_000,
    max_output_tokens: int = 8_192,
    execution_targets: list[ExecutionTarget] | None = None,
) -> ModelEntry:
    return ModelEntry(
        provider=provider,
        vendor=vendor,
        model_id=model_id,
        display_name=display_name,
        release_channel=release_channel,
        snapshot_type=SnapshotType.pinned,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        pricing_tier=pricing_tier,
        latency_tier=LatencyTier.medium,
        input_price_per_million=input_price_per_million,
        ability=Ability(coding=5, reasoning=5, writing=5),
        tool_support=tool_support if tool_support is not None else [],
        vision_support=False,
        deprecation_status=DeprecationStatus.active,
        execution_targets=execution_targets or [],
    )


def make_classification(
    *,
    risk: Level = Level.low,
    approval_level: ApprovalLevel = ApprovalLevel.auto,
) -> Classification:
    return Classification(
        task_type=TaskType.coding,
        complexity=Level.low,
        risk=risk,
        context_tokens=1000,
        context_band=ContextBand.small,
        output_type=OutputType.code,
        tool_needs=[],
        approval_level=approval_level,
    )
