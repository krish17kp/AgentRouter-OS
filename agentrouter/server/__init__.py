"""Local REST API surface for AgentRouter OS (Phase P7)."""

from __future__ import annotations

from .app import app, create_app

__all__ = ["app", "create_app"]
