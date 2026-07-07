"""Load + validate YAML registries. Fail loud at the boundary (NFR-5)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .schema import ModelEntry, Provider


class RegistryError(Exception):
    """Raised on malformed registry data — CLI maps this to exit code 3."""


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise RegistryError(f"Registry file not found: {path} (run: agentrouter init)")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RegistryError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise RegistryError(f"{path}: expected a mapping at top level")
    return data


def load_providers(path: Path) -> dict[str, Provider]:
    data = _load_yaml(path)
    providers = {}
    for i, raw in enumerate(data.get("providers", [])):
        try:
            p = Provider(**raw)
        except ValidationError as e:
            raise RegistryError(f"{path}: providers[{i}] invalid: {e}") from e
        providers[p.id] = p
    if not providers:
        raise RegistryError(f"{path}: no providers defined")
    return providers


def load_models(path: Path, providers: dict[str, Provider]) -> tuple[list[ModelEntry], list[str]]:
    """Returns (models, warnings). Unresolved fallbacks warn; bad fields fail."""
    data = _load_yaml(path)
    models: list[ModelEntry] = []
    for i, raw in enumerate(data.get("models", [])):
        try:
            m = ModelEntry(**raw)
        except ValidationError as e:
            mid = raw.get("model_id", f"index {i}") if isinstance(raw, dict) else f"index {i}"
            raise RegistryError(f"{path}: model '{mid}' invalid: {e}") from e
        if m.provider not in providers:
            raise RegistryError(
                f"{path}: model '{m.model_id}' references unknown provider '{m.provider}'"
            )
        models.append(m)
    if not models:
        raise RegistryError(f"{path}: no models defined")

    # unique model_id per provider
    seen: set[str] = set()
    for m in models:
        if m.key in seen:
            raise RegistryError(f"{path}: duplicate model '{m.key}'")
        seen.add(m.key)

    # unresolved fallbacks: warning, not fatal (spec §3)
    known_ids = {m.model_id for m in models}
    warnings = [
        f"model '{m.model_id}': fallback '{fb}' does not resolve to a known model_id"
        for m in models
        for fb in m.fallback
        if fb not in known_ids
    ]
    return models, warnings


def load_all_models(reg_dir: Path, providers: dict[str, Provider]) -> tuple[list[ModelEntry], list[str]]:
    """Manual models.yaml + any models.*.generated.yaml (from providers refresh).

    Manual entries win on key collision, so hand-edits are never shadowed and
    deleting a generated file cleanly reverts to the manual registry.
    """
    models, warnings = load_models(reg_dir / "models.yaml", providers)
    seen = {m.key for m in models}
    for gen_path in sorted(reg_dir.glob("models.*.generated.yaml")):
        gen_models, gen_warnings = load_models(gen_path, providers)
        warnings.extend(gen_warnings)
        for m in gen_models:
            if m.key in seen:
                warnings.append(f"{gen_path.name}: '{m.key}' shadowed by manual models.yaml")
                continue
            seen.add(m.key)
            models.append(m)
    return models, warnings
