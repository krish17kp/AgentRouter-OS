"""AgentRouter OS — CLI-first AI task-routing planner (MVP)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentrouter-os")
except PackageNotFoundError:  # source tree without an install — single source of truth is pyproject
    __version__ = "0.0.0+unknown"
