"""Exercise defensive registry error branches that protect malformed inputs."""

import pytest
import yaml

from agentrouter import registry


def test_registry_rejects_unhashable_yaml_mapping_key():
    with pytest.raises(yaml.constructor.ConstructorError, match="unhashable key"):
        registry._safe_load_yaml("? []\n: value\n")


def test_registry_rejects_empty_provider_and_model_catalogs(tmp_path):
    providers_path = tmp_path / "providers.yaml"
    providers_path.write_text("providers: []\n", encoding="utf-8")
    with pytest.raises(registry.RegistryError, match="no providers defined"):
        registry.load_providers(providers_path)

    models_path = tmp_path / "models.yaml"
    models_path.write_text("models: []\n", encoding="utf-8")
    with pytest.raises(registry.RegistryError, match="no models defined"):
        registry.load_models(models_path, {})


def test_registry_rejects_models_with_unconfigured_provider(home):
    providers = registry.load_providers(home / "registry" / "providers.yaml")
    models_path = home / "registry" / "models.yaml"
    original = models_path.read_text(encoding="utf-8")
    models_path.write_text(original.replace("provider: openai", "provider: missing-provider", 1))
    with pytest.raises(registry.RegistryError, match="references unknown provider"):
        registry.load_models(models_path, providers)


def test_registry_rejects_non_mapping_ability_overrides(home):
    models, warnings = registry.load_all_models(
        home / "registry", registry.load_providers(home / "registry" / "providers.yaml")
    )
    overrides_path = home / "registry" / registry.OVERRIDES_FILE
    overrides_path.write_text("overrides: []\n", encoding="utf-8")
    with pytest.raises(registry.RegistryError, match="expected an 'overrides' mapping"):
        registry._apply_ability_overrides(home / "registry", models, warnings)
