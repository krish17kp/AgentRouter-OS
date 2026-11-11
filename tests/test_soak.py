"""Deterministic coverage for the operator-triggered soak report."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from agentrouter.reliability import soak as soak_module


def test_resource_samples_cover_empty_growth_and_unavailable_platforms(monkeypatch, tmp_path):
    result = soak_module.SoakResult()
    assert result.growth("rss_kb") == (0, 0, 0.0)
    assert result.as_dict()["cycles"] == 0
    monkeypatch.setattr(soak_module, "resource", None)
    assert soak_module._rss_kb() == -1

    monkeypatch.setattr(soak_module.os, "listdir", lambda _path: (_ for _ in ()).throw(OSError()))
    assert soak_module._open_fds() == -1
    assert soak_module._size(tmp_path / "missing") == 0


def test_resource_samples_report_supported_platform_values(monkeypatch, tmp_path):
    monkeypatch.setattr(
        soak_module,
        "resource",
        SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _who: SimpleNamespace(ru_maxrss=42)),
    )
    assert soak_module._rss_kb() == 42
    # The production sampler intentionally reports -1 outside Linux because
    # `/proc/<pid>/fd` is not a portable interface.
    fd_count = soak_module._open_fds()
    if sys.platform == "linux":
        assert fd_count >= 0
    else:
        assert fd_count == -1
    path = tmp_path / "database"
    path.write_bytes(b"abc")
    assert soak_module._size(path) == 3


def test_soak_aggregates_a_sampled_load_without_sleeping(monkeypatch, tmp_path):
    class App:
        url = "http://127.0.0.1:1234"

    class Serve:
        def __enter__(self):
            return App()

        def __exit__(self, *_args):
            return False

    outcome = SimpleNamespace(ok=3, server_errors=0, transport_errors={"timeout": 1})
    clock = iter([0.0, 0.1, 0.2, 2.0])
    monkeypatch.setattr(soak_module.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(soak_module, "serve_app", lambda _home: Serve())
    monkeypatch.setattr(soak_module, "run_load", lambda _url, _spec: outcome)
    monkeypatch.setattr(soak_module, "_rss_kb", lambda: 10)
    monkeypatch.setattr(soak_module, "_open_fds", lambda: 4)

    result = soak_module.soak(tmp_path, seconds=1, workers=2, batch=3)

    assert result.total_ok == 3
    assert result.transport_errors == {"timeout": 1}
    assert result.samples[0].ok == 3
    assert result.samples[0].db_bytes == 0
    assert result.as_dict()["resource_trend_indicative_only"]["rss_kb"]["first"] == 10


def _install_fake_cli_runner(monkeypatch, exit_code=0):
    class FakeRunner:
        def invoke(self, _app, _args):
            return SimpleNamespace(exit_code=exit_code)

    monkeypatch.setitem(sys.modules, "typer.testing", SimpleNamespace(CliRunner=FakeRunner))


def test_soak_main_reports_init_failure(monkeypatch, tmp_path, capsys):
    _install_fake_cli_runner(monkeypatch, exit_code=1)
    assert soak_module.main(["--home", str(tmp_path), "--seconds", "0"]) == 1
    assert "could not initialise" in capsys.readouterr().err


def test_soak_main_writes_success_report(monkeypatch, tmp_path, capsys):
    _install_fake_cli_runner(monkeypatch)
    result = soak_module.SoakResult(total_ok=5)
    monkeypatch.setattr(soak_module, "soak", lambda *_args, **_kwargs: result)
    destination = tmp_path / "reports" / "soak.json"

    assert (
        soak_module.main(["--home", str(tmp_path), "--seconds", "0", "--out", str(destination)])
        == 0
    )
    assert '"total_ok": 5' in destination.read_text(encoding="utf-8")
    assert "SOAK OK" in capsys.readouterr().err


def test_soak_main_fails_on_server_or_transport_errors(monkeypatch, tmp_path, capsys):
    _install_fake_cli_runner(monkeypatch)
    monkeypatch.setattr(
        soak_module,
        "soak",
        lambda *_args, **_kwargs: soak_module.SoakResult(total_server_errors=1),
    )
    assert soak_module.main(["--home", str(tmp_path), "--seconds", "0"]) == 1
    assert "SOAK FAILED" in capsys.readouterr().err
