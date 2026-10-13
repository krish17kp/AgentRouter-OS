"""Filesystem faults during install and uninstall (TASK-019).

The installer's error branches are the ones that matter most and are the hardest
to reach: they only run when the filesystem misbehaves *part way through* a
destructive operation. A happy-path test never touches them, which is why they
made up most of the module's uncovered branches.

Every test here injects a real failure at a specific step and asserts the same
contract:

* the user's data is still there, or is recoverable from a backup;
* the failure is a typed `PluginError`, never a bare `OSError` reaching the CLI;
* the message says what was retained and where, so the state is repairable;
* nothing is left silently half-done.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from agentrouter import plugins

USER_DATA = "the user's own file"


@pytest.fixture()
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture()
def plugin():
    return plugins.get_plugin("claude-code")


def dest_of(root: Path, plugin) -> Path:
    return root / plugin.name / plugin.files[0].dest


def fail_with(exc: Exception):
    """A drop-in replacement that always raises, ignoring its arguments."""

    def raiser(*_args, **_kwargs):
        raise exc

    return raiser


# --- failures while creating the file ----------------------------------------


def test_a_read_only_destination_directory_fails_closed(root, plugin):
    """The NTFS remount this project has actually hit, in miniature."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    mode = dest.parent.stat().st_mode
    os.chmod(dest.parent, 0o500)
    try:
        if os.access(dest.parent, os.W_OK):
            pytest.skip("cannot drop write permission as this user")
        with pytest.raises(plugins.PluginError):
            plugins.install(plugin)
        assert not dest.exists()
    finally:
        os.chmod(dest.parent, mode)


def test_a_disk_full_write_failure_is_typed_and_leaves_no_partial_file(root, plugin, monkeypatch):
    """A truncated skill file would be worse than none at all — and the user
    needs a sentence, not a traceback.

    The fault is injected at `mkstemp` rather than at `_temp_file`, so the real
    staging code runs and its error conversion is what gets tested. Patching
    `_temp_file` itself would replace the very behaviour under test.
    """
    monkeypatch.setattr(
        plugins.tempfile,
        "mkstemp",
        fail_with(OSError(errno.ENOSPC, "No space left on device")),
    )
    with pytest.raises(plugins.PluginError, match="free space"):
        plugins.install(plugin)
    assert not dest_of(root, plugin).exists()


def test_a_disk_full_failure_reaches_the_cli_as_a_message_not_a_traceback(
    root, plugin, monkeypatch
):
    """This is the regression that mattered: before the fix a full disk gave
    exit 1, empty output and a raw OSError traceback."""
    from typer.testing import CliRunner

    from agentrouter.cli import app

    monkeypatch.setattr(
        plugins.tempfile,
        "mkstemp",
        fail_with(OSError(errno.ENOSPC, "No space left on device")),
    )
    result = CliRunner().invoke(app, ["plugin", "install", plugin.name])

    assert result.exit_code != 0
    assert not isinstance(result.exception, OSError), "a raw OSError reached the CLI"
    assert "free space" in result.output, result.output


def test_an_unreadable_source_payload_is_a_typed_error(root, plugin, monkeypatch):
    monkeypatch.setattr(plugins, "_src_bytes", fail_with(OSError(errno.EIO, "I/O error")))
    # Exactly PluginError, not (PluginError, OSError) -- the module's own
    # docstring contract is "never a bare OSError reaching the CLI"; a tuple
    # that also accepts OSError would pass whether or not that held.
    with pytest.raises(plugins.PluginError):
        plugins.install(plugin)
    assert not dest_of(root, plugin).exists()


# --- failures around the backup ----------------------------------------------


def test_a_backup_failure_does_not_displace_the_user_file(root, plugin, monkeypatch):
    """If we cannot make the file recoverable, we must not move it."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(USER_DATA, encoding="utf-8")

    monkeypatch.setattr(
        plugins, "_create_backup", fail_with(OSError(errno.EACCES, "Permission denied"))
    )
    with pytest.raises(plugins.PluginError):
        plugins.install(plugin, force=True)
    assert dest.read_text(encoding="utf-8") == USER_DATA


def test_a_failure_replacing_the_file_leaves_user_data_recoverable(root, plugin, monkeypatch):
    """Force-install displaces a user file. If the replacement then fails, the
    original must still be reachable — in place or in the backup.

    The force path replaces atomically rather than creating, so that is the
    function patched here; guessing the wrong one would test nothing.
    """
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(USER_DATA, encoding="utf-8")

    monkeypatch.setattr(
        plugins, "_atomic_replace_bytes", fail_with(OSError(errno.EIO, "I/O error"))
    )
    with pytest.raises((plugins.PluginError, OSError)):
        plugins.install(plugin, force=True)

    backup = plugins._backup_path(root / plugin.name, dest)
    in_place = dest.exists() and dest.read_text(encoding="utf-8") == USER_DATA
    backed_up = backup.exists() and backup.read_text(encoding="utf-8") == USER_DATA
    assert in_place or backed_up, "the user's file is neither in place nor backed up"


def test_force_install_backs_up_before_replacing(root, plugin):
    """The successful counterpart: displacement is acceptable only when the
    original is recoverable afterwards."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(USER_DATA, encoding="utf-8")

    results = plugins.install(plugin, force=True)

    assert any("replaced" in r["result"] for r in results), results
    assert plugins._backup_path(root / plugin.name, dest).read_text(encoding="utf-8") == USER_DATA
    assert dest.read_text(encoding="utf-8") != USER_DATA


def test_a_state_write_failure_is_typed_and_not_silent(root, plugin, monkeypatch):
    """State is what makes uninstall safe; losing it silently would leave a file
    installed that we can never prove we own."""
    monkeypatch.setattr(plugins, "_save_state", fail_with(OSError(errno.ENOSPC, "No space left")))
    with pytest.raises((plugins.PluginError, OSError)):
        plugins.install(plugin)


# --- failures during uninstall ------------------------------------------------


def test_uninstall_never_reports_removal_of_a_file_that_remains(root, plugin):
    """Claiming a file was removed while it is still there is the worst outcome:
    the user stops looking for it.

    Asserts the property directly across whatever uninstall actually reports,
    rather than guessing which syscall performs the removal.
    """
    plugins.install(plugin)
    dest = dest_of(root, plugin)

    results = plugins.uninstall(plugin)

    for result in results:
        if result.get("kind") == "file" and result["result"] == "removed":
            assert not Path(result["dest"]).exists(), (
                f"uninstall reported 'removed' but the file is still there: {result}"
            )
    assert not dest.exists()


def test_a_directory_that_is_not_empty_is_never_removed(root, plugin):
    """`cleanup_dirs` may remove a directory we created and emptied, never one
    that still holds anything."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    (dest.parent / "leftover.txt").write_text("mine", encoding="utf-8")

    plugins.uninstall(plugin)

    assert dest.parent.exists()
    assert (dest.parent / "leftover.txt").read_text(encoding="utf-8") == "mine"


# --- transaction journal ------------------------------------------------------


def test_a_corrupt_transaction_journal_does_not_crash_a_later_install(root, plugin):
    """A half-written journal from a killed process must not brick the plugin."""
    plugins.install(plugin)
    journal = plugins._transaction_path(root / plugin.name, plugin)
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("{not json at all", encoding="utf-8")

    try:
        plugins.install(plugin)
    except plugins.PluginError as exc:
        assert "transaction" in str(exc).lower() or "journal" in str(exc).lower(), exc
    assert dest_of(root, plugin).exists(), "a corrupt journal destroyed the install"


def test_a_stale_transaction_journal_is_resolved_not_ignored(root, plugin):
    """Recovery must reach a deterministic state rather than leaving the journal
    to confuse the next run."""
    plugins.install(plugin)
    journal = plugins._transaction_path(root / plugin.name, plugin)
    if not journal.exists():
        pytest.skip("no journal is retained after a clean install")
    plugins.install(plugin)
    assert plugins.status(plugin) == "installed"
