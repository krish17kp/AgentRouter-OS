"""Dataset registry + evaluation profiles (program §7 profiles).

Maps dataset names to adapter factories and defines which datasets each profile
runs. Adapters are imported lazily so a missing optional adapter never breaks
`list-datasets` or a fast run that doesn't use it.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import DatasetAdapter

# name -> "module:ClassName" (lazy import to keep startup cheap + resilient)
_ADAPTERS: dict[str, str] = {
    "agentrouter-gold": "agentrouter_gold:AgentRouterGoldAdapter",
    "clinc150": "clinc150:CLINC150Adapter",
    "banking77": "banking77:Banking77Adapter",
    "massive": "massive:MassiveAdapter",
    "longbench-v2": "longbench_v2:LongBenchV2Adapter",
    "swebench": "swebench:SWEBenchAdapter",
    "llmrouterbench": "llmrouterbench:LLMRouterBenchAdapter",
    "twinrouterbench": "twinrouterbench:TwinRouterBenchAdapter",
}

# which datasets each profile evaluates (offline-safe subsets only for fast/pr)
PROFILES: dict[str, list[str]] = {
    "fast": ["agentrouter-gold"],
    "pr": ["agentrouter-gold"],
    "nightly": ["agentrouter-gold", "clinc150", "banking77", "massive"],
    "release": [
        "agentrouter-gold",
        "clinc150",
        "banking77",
        "massive",
        "longbench-v2",
    ],
    "full": list(_ADAPTERS),
}


def dataset_names() -> list[str]:
    return list(_ADAPTERS)


def get_adapter(name: str) -> DatasetAdapter:
    if name not in _ADAPTERS:
        raise KeyError(f"unknown dataset '{name}'. Known: {', '.join(_ADAPTERS)}")
    module_name, class_name = _ADAPTERS[name].split(":")
    import importlib

    mod = importlib.import_module(f".adapters.{module_name}", package=__package__)
    return getattr(mod, class_name)()


def try_get_adapter(name: str) -> DatasetAdapter | None:
    """Best-effort load — returns None if the adapter module isn't available."""
    try:
        return get_adapter(name)
    except Exception:  # noqa: BLE001 - resilience for optional adapters
        return None


def profile_datasets(profile: str) -> list[str]:
    if profile not in PROFILES:
        raise KeyError(f"unknown profile '{profile}'. Known: {', '.join(PROFILES)}")
    return PROFILES[profile]


def available_adapters() -> list[tuple[str, Callable[[], DatasetAdapter]]]:
    return [(n, lambda n=n: get_adapter(n)) for n in _ADAPTERS]
