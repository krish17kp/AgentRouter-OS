"""Run the reliability soak profile as ``python -m agentrouter.reliability``."""

from __future__ import annotations

from .soak import main

if __name__ == "__main__":  # pragma: no cover - exercised by subprocess smoke tests
    raise SystemExit(main())
