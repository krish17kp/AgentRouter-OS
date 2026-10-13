"""What the plugin installer's safety proofs do and do not cover (TASK-019).

`agentrouter/plugins.py` has two genuinely different implementations of the most
destructive operation. On POSIX, `_remove_directory_by_handle` opens the parent
with `O_NOFOLLOW|O_DIRECTORY`, verifies `(st_dev, st_ino)` and calls `rmdir`
with `dir_fd`. On Windows there is no `dir_fd` form, so it goes through
`CreateFileW` with `FILE_FLAG_OPEN_REPARSE_POINT` and marks the handle for
deletion.

The adversarial suite in `test_plugins_adversarial.py` runs on POSIX. **Passing
there says nothing about the Windows path**, and this file exists so that
distinction is enforced rather than merely written down somewhere: the Windows
branch is only claimed as verified where a Windows runner actually executes it.

The CI matrix includes `test-windows`, so the parametrised lifecycle tests below
do run on both — but the link-specific attacks cannot be expressed portably, and
pretending otherwise would be the exact overclaim this project keeps finding.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentrouter import plugins

WINDOWS = os.name == "nt"


@pytest.fixture()
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture()
def plugin():
    return plugins.get_plugin("claude-code")


# --- portable lifecycle: must hold identically on every platform -------------


@pytest.mark.parametrize("plugin_name", ["claude-code", "codex"])
def test_the_full_lifecycle_is_portable(root, plugin_name):
    """install -> reinstall -> uninstall -> reinstall, on whatever OS runs this.

    Path separators, case behaviour and replacement semantics all differ between
    platforms; the observable lifecycle must not.
    """
    p = plugins.get_plugin(plugin_name)
    assert plugins.status(p) == "not-installed"

    first = plugins.install(p)
    assert any(r["result"] == "created" for r in first), first
    assert plugins.status(p) == "installed"

    second = plugins.install(p)
    assert all("skipped" in r["result"] for r in second), second

    plugins.uninstall(p)
    assert plugins.status(p) == "not-installed"

    third = plugins.install(p)
    assert any(r["result"] == "created" for r in third), third
    assert plugins.status(p) == "installed"


def test_destination_resolution_stays_inside_the_root_on_this_platform(root, plugin):
    """`_safe_dest` is the containment boundary; it must hold with this OS's
    own path semantics, not just POSIX ones."""
    dest = plugins._safe_dest(plugins.dest_root(plugin), plugin.files[0].dest)
    assert dest.resolve().is_relative_to(root.resolve())


@pytest.mark.parametrize("hostile", ["../out.md", "a/../../out.md", "./../x"])
def test_traversal_is_rejected_on_this_platform(hostile):
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative(hostile, "plugin destination")


@pytest.mark.skipif(not WINDOWS, reason="Windows-only path separator semantics")
def test_a_backslash_separator_is_rejected_on_windows():
    """On Windows a backslash is a real separator, so it is a traversal vector
    that POSIX tests cannot express."""
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative("..\\escape.md", "plugin destination")


# --- the honest boundary ------------------------------------------------------


@pytest.mark.skipif(WINDOWS, reason="POSIX link semantics")
def test_posix_link_defences_are_exercised_here_only(root, plugin, tmp_path):
    """A marker test, deliberately explicit.

    The link attacks in `test_plugins_adversarial.py` prove the POSIX branch of
    `_is_link_or_reparse` and `_remove_directory_by_handle`. They do NOT prove
    the Windows `CreateFileW` / reparse-point branch, which is different code.
    """
    victim = tmp_path / "outside.txt"
    victim.write_text("user data", encoding="utf-8")
    dest = plugins._safe_dest(plugins.dest_root(plugin), plugin.files[0].dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(victim)

    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(plugin)
    assert victim.read_text(encoding="utf-8") == "user data"


@pytest.mark.skipif(not WINDOWS, reason="requires a Windows runner")
def test_windows_directory_removal_uses_the_handle_based_path(root, plugin):
    """Exercises the Windows branch of the destructive path on a real runner.

    This is the only evidence in the repository about that branch. If this test
    does not run, the Windows reparse-point behaviour is UNVERIFIED and must not
    be described as guaranteed.
    """
    plugins.install(plugin)
    dest = plugins._safe_dest(plugins.dest_root(plugin), plugin.files[0].dest)
    assert dest.exists()

    plugins.uninstall(plugin)

    assert not dest.exists()
    assert not dest.parent.exists(), "the owned empty directory was not removed"
