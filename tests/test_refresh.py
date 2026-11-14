"""Capstone M2 — providers refresh (OpenRouter) with mocked HTTP. No network, no keys."""

import copy
import os
import urllib.error

import pytest
import yaml
from typer.testing import CliRunner

import agentrouter.refresh as refresh
from agentrouter.refresh import (
    RefreshError,
    fetch_openrouter_models,
    map_openrouter_model,
    write_generated_registry,
)
from agentrouter.registry import load_all_models, load_providers
from agentrouter.schema import PricingTier

runner = CliRunner()

SAMPLE_RESPONSE = {
    "data": [
        {
            "id": "vendor/frontier-x",
            "name": "Frontier X",
            "context_length": 200000,
            "pricing": {"prompt": "0.00002", "completion": "0.0001"},
            "supported_parameters": ["tools", "temperature"],
            "architecture": {"input_modalities": ["text", "image"]},
            "top_provider": {"max_completion_tokens": 32000},
        },
        {
            "id": "vendor/cheap-y",
            "name": "Cheap Y",
            "context_length": 32000,
            "pricing": {"prompt": "0"},
            "supported_parameters": [],
            "architecture": {"input_modalities": ["text"]},
        },
        {"id": "vendor/broken-no-context", "pricing": {"prompt": "0.000001"}},
        {
            "id": "vendor/mid-z",
            "name": "Mid Z",
            "context_length": 128000,
            "pricing": {"prompt": "0.000002"},
            "supported_parameters": ["tools"],
            "architecture": {"input_modalities": ["text"]},
        },
    ]
}


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from agentrouter.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


@pytest.fixture()
def mock_http(monkeypatch):
    """Serve SAMPLE_RESPONSE instead of hitting the network."""
    calls = []

    def fake(url, api_key):
        calls.append({"url": url, "api_key": api_key})
        return copy.deepcopy(SAMPLE_RESPONSE)

    monkeypatch.setattr(refresh, "_http_get_json", fake)
    return calls


# --- mapping ------------------------------------------------------------------


@pytest.mark.parametrize(
    "price,tier",
    [
        (0.0, PricingTier.free),
        (5e-7, PricingTier.low),
        (2e-6, PricingTier.medium),
        (1e-5, PricingTier.high),
        (2e-5, PricingTier.frontier),
    ],
)
def test_pricing_tier_mapping(price, tier):
    assert refresh._pricing_tier(price) is tier


def test_map_entry_full_fields():
    m = map_openrouter_model(SAMPLE_RESPONSE["data"][0])
    assert m.key == "openrouter/vendor/frontier-x"
    assert m.pricing_tier is PricingTier.frontier
    assert m.ability.coding == 9
    assert m.tool_support == ["tool-use", "function-calling"]
    assert m.vision_support is True
    assert m.max_output_tokens == 32000
    assert m.source == "refresh"
    assert m.deprecation_status.value == "active"


def test_map_entry_minimal_fields():
    m = map_openrouter_model(SAMPLE_RESPONSE["data"][1])
    assert m.pricing_tier is PricingTier.free
    assert m.tool_support == []
    assert m.vision_support is False
    assert m.max_output_tokens == 32000 // 4  # derived when provider omits it


def test_map_entry_missing_context_raises():
    with pytest.raises(RefreshError, match="context_length"):
        map_openrouter_model(SAMPLE_RESPONSE["data"][2])


# --- fetch --------------------------------------------------------------------


def test_fetch_skips_bad_entries_with_warning(mock_http):
    entries, warnings = fetch_openrouter_models(None, limit=25)
    assert [e.model_id for e in entries] == ["vendor/frontier-x", "vendor/cheap-y", "vendor/mid-z"]
    assert len(warnings) == 1 and "broken-no-context" in warnings[0]


def test_fetch_respects_limit(mock_http):
    entries, _ = fetch_openrouter_models(None, limit=1)
    assert len(entries) == 1


def test_fetch_bad_shape_raises(monkeypatch):
    monkeypatch.setattr(refresh, "_http_get_json", lambda url, api_key: {"error": "nope"})
    with pytest.raises(RefreshError, match="response shape"):
        fetch_openrouter_models(None, limit=5)


def test_openai_refresh_maps_known_models_and_warns_for_unmapped(monkeypatch):
    calls = []

    def fake(url, api_key):
        calls.append((url, api_key))
        return {"data": [{"id": "gpt-4.1-mini-2026-01-01"}, {"id": "text-embedding-3-small"}]}

    monkeypatch.setattr(refresh, "_http_get_json", fake)
    entries, warnings = refresh.fetch_openai_models("test-key", limit=10)
    assert calls == [(refresh.OPENAI_MODELS_URL, "test-key")]
    assert [entry.model_id for entry in entries] == ["gpt-4.1-mini-2026-01-01"]
    assert warnings == ["skipped 1 catalog entries with no family mapping (non-chat or unknown)"]


def test_openai_refresh_requires_key_and_valid_catalog(monkeypatch):
    with pytest.raises(RefreshError, match="OPENAI_API_KEY"):
        refresh.fetch_openai_models(None, limit=5)

    monkeypatch.setattr(refresh, "_http_get_json", lambda *_args: {"data": []})
    with pytest.raises(RefreshError, match="response shape"):
        refresh.fetch_openai_models("test-key", limit=5)


@pytest.mark.parametrize(
    ("payload", "match", "message"),
    [
        ({"data": [{"id": "unknown-model"}]}, None, "no OpenAI entry could be mapped"),
        ({"data": [{"id": "gpt-4o"}]}, "missing", "no OpenAI entry matched"),
    ],
)
def test_openai_refresh_reports_empty_filtered_results(monkeypatch, payload, match, message):
    monkeypatch.setattr(refresh, "_http_get_json", lambda *_args: payload)
    with pytest.raises(RefreshError, match=message):
        refresh.fetch_openai_models("test-key", limit=5, match=match)


def test_http_get_json_rejects_non_http_schemes():
    with pytest.raises(RefreshError, match=r"non-http\(s\)"):
        refresh._http_get_json("file:///etc/passwd", None)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (urllib.error.HTTPError("https://example.test", 503, "down", {}, None), "HTTP 503"),
        (urllib.error.URLError("offline"), "network error"),
        (TimeoutError("slow"), "timed out"),
    ],
)
def test_http_get_json_converts_transport_failures(monkeypatch, failure, message):
    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(refresh.urllib.request, "urlopen", fail)
    with pytest.raises(RefreshError, match=message):
        refresh._http_get_json("https://example.test/models", "secret")


def test_http_get_json_converts_invalid_json_and_adds_auth_header(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{invalid"

    def fake_urlopen(request, timeout):
        captured["auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(refresh.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RefreshError, match="not valid JSON"):
        refresh._http_get_json("https://example.test/models", "secret")
    assert captured == {"auth": "Bearer secret", "timeout": refresh._TIMEOUT_SECONDS}


def test_http_get_json_accepts_valid_json_without_an_api_key(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data": []}'

    monkeypatch.setattr(refresh.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    assert refresh._http_get_json("https://example.test/models", None) == {"data": []}


def test_openai_refresh_stops_after_requested_limit(monkeypatch):
    monkeypatch.setattr(
        refresh,
        "_http_get_json",
        lambda *_args: {"data": [{"id": "gpt-4o"}, {"id": "gpt-5"}]},
    )
    entries, warnings = refresh.fetch_openai_models("test-key", limit=1)
    assert [entry.model_id for entry in entries] == ["gpt-4o"]
    assert warnings == []


# --- generated registry merge ---------------------------------------------------


def test_manual_wins_on_collision(home, mock_http):
    reg_dir = home / "registry"
    providers = load_providers(reg_dir / "providers.yaml")
    manual_models, _ = load_all_models(reg_dir, providers)
    manual_entry = next(m for m in manual_models if m.model_id == "claude-sonnet-5")

    clone = manual_entry.model_copy(update={"pricing_tier": PricingTier.free, "source": "refresh"})
    write_generated_registry(reg_dir, "openrouter", [clone])
    merged, warnings = load_all_models(reg_dir, providers)

    kept = [m for m in merged if m.model_id == "claude-sonnet-5"]
    assert len(kept) == 1 and kept[0].pricing_tier is PricingTier.high  # manual value
    assert any("shadowed" in w for w in warnings)


def test_write_generated_registry_includes_provenance(home, mock_http):
    entries, _ = fetch_openrouter_models(None, limit=25)
    reg_dir = home / "registry"
    path = write_generated_registry(
        reg_dir, "openrouter", entries, cli_args={"limit": 25, "match": None}
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    prov = data["provenance"]
    assert prov["provider"] == "openrouter"
    assert prov["source_url"] == refresh.OPENROUTER_MODELS_URL
    assert prov["count"] == len(entries)
    assert prov["cli_args"] == {"limit": 25, "match": None}
    assert prov["tool_version"]
    assert prov["fetched_at"]  # ISO-8601 UTC timestamp, non-empty


def test_write_generated_registry_provenance_ignored_by_loader(home, mock_http):
    """Extra top-level `provenance` key must not break the registry loader."""
    entries, _ = fetch_openrouter_models(None, limit=25)
    reg_dir = home / "registry"
    write_generated_registry(reg_dir, "openrouter", entries)
    providers = load_providers(reg_dir / "providers.yaml")
    merged, _ = load_all_models(reg_dir, providers)
    assert any(m.source == "refresh" for m in merged)


def test_write_generated_registry_is_atomic_on_failure(home, mock_http, monkeypatch):
    """A failure during the atomic replace must never corrupt the previous file."""
    entries, _ = fetch_openrouter_models(None, limit=25)
    reg_dir = home / "registry"
    path = write_generated_registry(reg_dir, "openrouter", entries)
    original = path.read_text(encoding="utf-8")

    def boom(_src, _dst):
        raise OSError("simulated crash during atomic replace")

    monkeypatch.setattr(refresh.os, "replace", boom)
    with pytest.raises(OSError, match="simulated crash"):
        write_generated_registry(reg_dir, "openrouter", entries[:1])

    # the final file is untouched — still the original, complete content
    assert path.read_text(encoding="utf-8") == original
    # no leftover temp file (hidden, unpredictable name — glob for the *.tmp suffix)
    assert not list(reg_dir.glob("*.tmp"))


def test_write_generated_registry_temp_file_is_not_predictable(home, mock_http):
    """The temp filename must not be guessable/pre-plantable (no fixed name + PID)."""
    entries, _ = fetch_openrouter_models(None, limit=25)
    reg_dir = home / "registry"
    predictable = reg_dir / f"models.openrouter.generated.yaml.tmp{os.getpid()}"
    write_generated_registry(reg_dir, "openrouter", entries)
    assert not predictable.exists()


def test_previous_model_ids_reads_existing_generated_file(home, mock_http):
    entries, _ = fetch_openrouter_models(None, limit=25)
    reg_dir = home / "registry"
    assert refresh.previous_model_ids(reg_dir, "openrouter") == set()
    write_generated_registry(reg_dir, "openrouter", entries)
    assert refresh.previous_model_ids(reg_dir, "openrouter") == {e.model_id for e in entries}


@pytest.mark.parametrize("content", ["[1, 2]", "models: nope\n", "models: [\n", "\xff"])
def test_previous_model_ids_ignores_invalid_or_unexpected_files(tmp_path, content):
    path = tmp_path / "models.openrouter.generated.yaml"
    path.write_bytes(content.encode("latin-1"))
    assert refresh.previous_model_ids(tmp_path, "openrouter") == set()


def test_refresh_is_idempotent(home, mock_http):
    from agentrouter.cli import app

    for _ in range(2):
        r = runner.invoke(app, ["providers", "refresh", "openrouter"])
        assert r.exit_code == 0, r.output
    reg_dir = home / "registry"
    providers = load_providers(reg_dir / "providers.yaml")
    merged, _ = load_all_models(reg_dir, providers)
    assert len([m for m in merged if m.source == "refresh"]) == 3  # no duplicates


# --- CLI ------------------------------------------------------------------------


def test_cli_refresh_writes_and_routing_still_works(home, mock_http):
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter", "--limit", "10"])
    assert r.exit_code == 0, r.output
    gen = home / "registry" / "models.openrouter.generated.yaml"
    assert gen.exists()
    data = yaml.safe_load(gen.read_text(encoding="utf-8"))
    assert len(data["models"]) == 3

    lst = runner.invoke(app, ["registry", "list"])
    assert "vendor/frontier-x" in lst.output  # refreshed model visible
    assert "claude-sonnet-5" in lst.output  # manual registry preserved

    route = runner.invoke(app, ["route", "write a haiku about routers"])
    assert route.exit_code == 0, route.output


def test_cli_refresh_reports_deprecation_candidates(home, mock_http, monkeypatch):
    from agentrouter.cli import app

    r1 = runner.invoke(app, ["providers", "refresh", "openrouter"])
    assert r1.exit_code == 0, r1.output
    assert "candidate deprecation" not in r1.output  # nothing to compare against yet

    shrunk = copy.deepcopy(SAMPLE_RESPONSE)
    shrunk["data"] = [shrunk["data"][0]]  # only vendor/frontier-x remains live

    def fake_shrunk(url, api_key):
        return copy.deepcopy(shrunk)

    monkeypatch.setattr(refresh, "_http_get_json", fake_shrunk)
    r2 = runner.invoke(app, ["providers", "refresh", "openrouter"])
    assert r2.exit_code == 0, r2.output
    assert "candidate deprecation" in r2.output
    assert "vendor/cheap-y" in r2.output and "vendor/mid-z" in r2.output
    assert "nothing is deleted" in r2.output

    # report-only: the new fetch still overwrites the generated file (no auto-keep)
    gen = home / "registry" / "models.openrouter.generated.yaml"
    data = yaml.safe_load(gen.read_text(encoding="utf-8"))
    assert [m["model_id"] for m in data["models"]] == ["vendor/frontier-x"]


def test_cli_refresh_dry_run_writes_nothing(home, mock_http):
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter", "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Dry run" in r.output
    assert not (home / "registry" / "models.openrouter.generated.yaml").exists()


def test_cli_refresh_network_error_exit1(home, monkeypatch):
    def boom(url, api_key):
        raise RefreshError("network error reaching https://example: unreachable")

    monkeypatch.setattr(refresh, "_http_get_json", boom)
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter"])
    assert r.exit_code == 1
    assert "registry was NOT modified" in r.output and "Next:" in r.output


def test_cli_refresh_unsupported_provider_exit2(home):
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "cursor"])
    assert r.exit_code == 2
    assert "not refreshable" in r.output and "openrouter" in r.output


def test_cli_refresh_never_prints_key(home, mock_http, monkeypatch):
    secret = "sk-or-test-DO-NOT-PRINT-000"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter"])
    assert r.exit_code == 0, r.output
    assert secret not in r.output
    assert "using OPENROUTER_API_KEY from environment" in r.output
    assert mock_http[0]["api_key"] == secret  # key went to the header path only


def test_cli_refresh_works_without_key(home, mock_http):
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter"])
    assert r.exit_code == 0, r.output
    assert "public catalog endpoint" in r.output
    assert mock_http[0]["api_key"] is None


# --- M3: --match filter -------------------------------------------------------------


def test_fetch_match_filters_by_substring(mock_http):
    entries, _ = fetch_openrouter_models(None, limit=25, match="frontier")
    assert [e.model_id for e in entries] == ["vendor/frontier-x"]


def test_fetch_match_nothing_raises(mock_http):
    with pytest.raises(RefreshError, match="--match"):
        fetch_openrouter_models(None, limit=25, match="does-not-exist")


def test_cli_refresh_match(home, mock_http):
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openrouter", "--match", "cheap"])
    assert r.exit_code == 0, r.output
    data = yaml.safe_load(
        (home / "registry" / "models.openrouter.generated.yaml").read_text(encoding="utf-8")
    )
    assert [m["model_id"] for m in data["models"]] == ["vendor/cheap-y"]


# --- M3: OpenAI adapter ---------------------------------------------------------------

OPENAI_RESPONSE = {
    "data": [
        {"id": "gpt-4o-mini-2024-07-18", "object": "model", "owned_by": "system"},
        {"id": "gpt-4.1", "object": "model", "owned_by": "system"},
        {"id": "whisper-1", "object": "model", "owned_by": "system"},
        {"id": "text-embedding-3-small", "object": "model", "owned_by": "system"},
        {"id": "o4-mini", "object": "model", "owned_by": "system"},
    ]
}


@pytest.fixture()
def mock_openai_http(monkeypatch):
    calls = []

    def fake(url, api_key):
        calls.append({"url": url, "api_key": api_key})
        return copy.deepcopy(OPENAI_RESPONSE)

    monkeypatch.setattr(refresh, "_http_get_json", fake)
    return calls


def test_map_openai_prefix_match():
    m = refresh.map_openai_model({"id": "gpt-4o-mini-2024-07-18"})
    assert m.key == "openai/gpt-4o-mini-2024-07-18"
    assert m.pricing_tier is PricingTier.low
    assert m.context_window == 128_000
    assert m.tool_support == ["tool-use", "function-calling"]
    assert m.source == "refresh"


def test_map_openai_longest_prefix_wins():
    # gpt-4o-mini must map to the mini family, not plain gpt-4o
    mini = refresh.map_openai_model({"id": "gpt-4o-mini"})
    full = refresh.map_openai_model({"id": "gpt-4o"})
    assert mini.pricing_tier is PricingTier.low
    assert full.pricing_tier is PricingTier.medium


def test_map_openai_unknown_family_raises():
    with pytest.raises(RefreshError, match="family"):
        refresh.map_openai_model({"id": "whisper-1"})


def test_fetch_openai_requires_key(mock_openai_http):
    with pytest.raises(RefreshError, match="OPENAI_API_KEY"):
        refresh.fetch_openai_models(None, limit=25)
    assert mock_openai_http == []  # no request without a key


def test_fetch_openai_maps_and_aggregates_skips(mock_openai_http):
    entries, warnings = refresh.fetch_openai_models("sk-test", limit=25)
    assert [e.model_id for e in entries] == ["gpt-4o-mini-2024-07-18", "gpt-4.1", "o4-mini"]
    assert len(warnings) == 1 and "skipped 2" in warnings[0]
    assert mock_openai_http[0]["api_key"] == "sk-test"


def test_cli_refresh_openai_end_to_end(home, mock_openai_http, monkeypatch):
    secret = "sk-test-DO-NOT-PRINT"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openai"])
    assert r.exit_code == 0, r.output
    assert secret not in r.output
    gen = home / "registry" / "models.openai.generated.yaml"
    assert gen.exists()
    lst = runner.invoke(app, ["registry", "list", "--provider", "openai"])
    assert "gpt-4.1" in lst.output


def test_cli_refresh_openai_without_key_exit1(home, mock_openai_http, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from agentrouter.cli import app

    r = runner.invoke(app, ["providers", "refresh", "openai"])
    assert r.exit_code == 1
    assert "OPENAI_API_KEY" in r.output
