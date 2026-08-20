"""Adversarial proof of the plugin installer's safety invariants (TASK-019).

`agentrouter/plugins.py` writes into user-controlled agent configuration
directories **outside this repository** and later removes files from them. Its
docstring claims it records ownership, refuses links and reparse points, and
never recursively removes directories.

Those claims turned out to be true. This file exists because "true today" is not
the same as "protected": every invariant below was verified by attacking a real
installer against a real temporary filesystem, and is pinned here so a later
refactor cannot quietly remove a defence. Each test states the damage it is
preventing, not the implementation it happens to use.

Scope note kept deliberately honest: these run on POSIX. The Windows
reparse-point and junction paths in `_remove_directory_by_handle` are a separate
code path that **cannot** be exercised here, and nothing in this file should be
read as evidence about them. See `test_plugins_platform.py`.
"""

from __future__ import annotations

import json
import os
import threading
from collections import Counter
from pathlib import Path

import pytest

from agentrouter import plugins

UNMANAGED = "a file AgentRouter never installed"
USER_EDIT = "the user's own customisation"


@pytest.fixture()
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture()
def plugin():
    return plugins.get_plugin("claude-code")


def dest_of(root: Path, plugin) -> Path:
    return root / plugin.name / plugin.files[0].dest


def outside_file(tmp_path: Path, name: str, content: str) -> Path:
    """A file that belongs to the user and lives outside any plugin root."""
    victim = tmp_path / "elsewhere" / name
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text(content, encoding="utf-8")
    return victim


# --- writes must never escape the plugin root --------------------------------


def test_a_symlinked_destination_is_refused_and_the_target_untouched(root, plugin, tmp_path):
    """Otherwise installing a skill silently overwrites whatever it points at."""
    victim = outside_file(tmp_path, "victim.txt", UNMANAGED)
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(victim)

    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(plugin)
    assert victim.read_text(encoding="utf-8") == UNMANAGED


def test_a_symlinked_parent_directory_is_refused(root, plugin, tmp_path):
    """The destination itself can be clean while a parent redirects the write."""
    outside = tmp_path / "elsewhere" / "redirected"
    outside.mkdir(parents=True)
    skills = root / plugin.name / "skills"
    skills.parent.mkdir(parents=True, exist_ok=True)
    skills.symlink_to(outside, target_is_directory=True)

    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(plugin)
    assert list(outside.iterdir()) == [], "content was written outside the plugin root"


def test_a_dangling_symlink_destination_is_refused(root, plugin, tmp_path):
    """A dangling link would otherwise be 'created' at an attacker-chosen path."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(tmp_path / "elsewhere" / "does-not-exist-yet")

    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(plugin)
    assert not (tmp_path / "elsewhere" / "does-not-exist-yet").exists()


def test_a_hardlinked_destination_is_refused_and_the_target_untouched(root, plugin, tmp_path):
    """A hardlink is invisible to a symlink check and resolves inside the root,
    so writing through it edits the user's file with no link to follow."""
    victim = outside_file(tmp_path, "hard.txt", UNMANAGED)
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.link(victim, dest)

    with pytest.raises(plugins.PluginError, match="hard link"):
        plugins.install(plugin)
    assert victim.read_text(encoding="utf-8") == UNMANAGED


@pytest.mark.parametrize(
    "hostile",
    ["../escape.md", "/etc/passwd", "a/../../escape.md", "./../../x"],
)
def test_a_relative_path_cannot_escape_the_plugin_root(hostile):
    """`_safe_relative` is the only thing between a plugin manifest and an
    arbitrary-file write."""
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative(hostile, "plugin destination")


# --- uninstall must never remove what it does not own ------------------------


def test_uninstall_preserves_a_file_the_user_edited(root, plugin):
    """The whole point of recording a digest: an edited file is no longer ours."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    dest.write_text(USER_EDIT, encoding="utf-8")

    results = plugins.uninstall(plugin)

    assert dest.exists(), "an edited file was deleted"
    assert dest.read_text(encoding="utf-8") == USER_EDIT
    assert any("preserved" in r["result"] for r in results), results


def test_uninstall_preserves_an_unmanaged_file_at_the_destination(root, plugin):
    """A file that happens to sit where we would install is not ours to delete."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(UNMANAGED, encoding="utf-8")

    results = plugins.uninstall(plugin)

    assert dest.read_text(encoding="utf-8") == UNMANAGED
    assert all("preserved" in r["result"] for r in results), results


def test_uninstall_fails_closed_when_the_ownership_record_is_gone(root, plugin):
    """Without proof of ownership the safe answer is to keep the file, not to
    guess from the path."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    plugins._state_path(root / plugin.name, plugin).unlink()

    results = plugins.uninstall(plugin)

    assert dest.exists(), "a file was deleted with no ownership record"
    assert all("preserved" in r["result"] for r in results), results


def test_uninstall_does_not_recursively_remove_a_populated_directory(root, plugin):
    """`cleanup_dirs` must remove an empty directory we made, never a tree."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    sibling = dest.parent / "user-notes.md"
    sibling.write_text(UNMANAGED, encoding="utf-8")

    plugins.uninstall(plugin)

    assert sibling.read_text(encoding="utf-8") == UNMANAGED
    assert sibling.parent.exists(), "a directory holding user content was removed"


# --- upgrade: a new package version must not eat a user edit -----------------


def test_a_package_upgrade_replaces_an_untouched_managed_file(root, plugin, monkeypatch):
    """The path that only runs when the shipped payload actually changes."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    monkeypatch.setattr(plugins, "_src_bytes", lambda rel: b"# VERSION 2 PAYLOAD\n")

    results = plugins.install(plugin)

    assert dest.read_text(encoding="utf-8").strip() == "# VERSION 2 PAYLOAD"
    assert any("updated" in r["result"] for r in results), results


def test_a_package_upgrade_refuses_to_overwrite_a_user_edit(root, plugin, monkeypatch):
    """Upgrading the package must not be a way to discard someone's work."""
    plugins.install(plugin)
    dest = dest_of(root, plugin)
    dest.write_text(USER_EDIT, encoding="utf-8")
    monkeypatch.setattr(plugins, "_src_bytes", lambda rel: b"# VERSION 2 PAYLOAD\n")

    with pytest.raises(plugins.PluginError, match="refusing to overwrite the user edit"):
        plugins.install(plugin)
    assert dest.read_text(encoding="utf-8") == USER_EDIT


# --- backups ------------------------------------------------------------------


def test_install_refuses_to_clobber_a_pre_existing_backup(root, plugin):
    """A colliding backup means someone else's data is already parked there."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(UNMANAGED, encoding="utf-8")
    backup = plugins._backup_path(root / plugin.name, dest)
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("somebody else's backup", encoding="utf-8")

    with pytest.raises(plugins.PluginError, match="backup already exists"):
        plugins.install(plugin, force=True)
    assert dest.read_text(encoding="utf-8") == UNMANAGED
    assert backup.read_text(encoding="utf-8") == "somebody else's backup"


def test_force_install_backs_up_the_displaced_user_file(root, plugin):
    """Displacing a file is only acceptable if it is recoverable."""
    dest = dest_of(root, plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(UNMANAGED, encoding="utf-8")

    plugins.install(plugin, force=True)

    backup = plugins._backup_path(root / plugin.name, dest)
    assert backup.exists(), "the displaced user file was not recoverable"
    assert backup.read_text(encoding="utf-8") == UNMANAGED


# --- concurrency --------------------------------------------------------------


def test_concurrent_installs_produce_exactly_one_created_result(root, plugin):
    """Two agents installing at once must not both think they created it, and
    must not leave duplicate or partial files behind."""
    outcomes: list[tuple[str, ...]] = []
    failures: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        try:
            result = plugins.install(plugin)
            with guard:
                outcomes.append(tuple(r["result"] for r in result))
        except Exception as exc:  # noqa: BLE001 - a race must not raise
            with guard:
                failures.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == [], failures
    created = sum(1 for o in outcomes if o == ("created",))
    assert created == 1, Counter(outcomes)
    dest = dest_of(root, plugin)
    assert dest.exists()
    assert len(list(dest.parent.iterdir())) == 1, list(dest.parent.iterdir())


def test_concurrent_install_and_uninstall_never_raise_or_corrupt(root, plugin):
    """Interleaving the two most dangerous operations must serialise, not race
    into deleting a file another thread just wrote."""
    plugins.install(plugin)
    failures: list[str] = []
    guard = threading.Lock()

    def worker(install: bool) -> None:
        try:
            plugins.install(plugin) if install else plugins.uninstall(plugin)
        except Exception as exc:  # noqa: BLE001
            with guard:
                failures.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i % 2 == 0,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == [], failures
    # The real vocabulary from plugins.status(); "partial" would mean a file
    # was left half-written, which is the corruption this test exists to catch.
    assert plugins.status(plugin) in ("installed", "not-installed")


# --- ownership state ----------------------------------------------------------


def test_a_corrupt_ownership_record_does_not_crash_the_installer(root, plugin):
    """State is a file on disk; a truncated write must fail closed, not raise
    an unhandled exception into the CLI."""
    plugins.install(plugin)
    state = plugins._state_path(root / plugin.name, plugin)
    state.write_text("{not json", encoding="utf-8")

    try:
        results = plugins.uninstall(plugin)
    except plugins.PluginError:
        return  # failing closed with a typed error is the acceptable outcome
    assert all("preserved" in r["result"] for r in results), results
    assert dest_of(root, plugin).exists()


def test_the_ownership_record_never_contains_file_contents(root, plugin):
    """State travels in diagnostic bundles; it must carry digests, not payloads."""
    plugins.install(plugin)
    state = plugins._state_path(root / plugin.name, plugin)
    body = json.loads(state.read_text(encoding="utf-8"))
    blob = json.dumps(body)

    payload = plugins._src_bytes(plugin.files[0].src).decode("utf-8", "ignore")
    distinctive = [line for line in payload.splitlines() if len(line) > 30][:3]
    for line in distinctive:
        assert line not in blob, "the ownership record embedded file content"


def test_an_unknown_plugin_name_is_bounded_and_sanitised_before_echo():
    """The name comes from the caller and is echoed straight back.

    Unbounded, a 5 KB argument produced a 5 KB error message; with CR/LF intact
    it could forge extra lines in anything capturing CLI output. Same class of
    problem as the API's `decision_id`, so it uses the same shared helper rather
    than a second implementation that could drift.
    """
    with pytest.raises(plugins.PluginError) as huge:
        plugins.get_plugin("A" * 5000)
    assert len(str(huge.value)) < 200, "an oversized name produced an oversized error"

    with pytest.raises(plugins.PluginError) as hostile:
        plugins.get_plugin("x\r\nInjected-Line: yes‮")
    message = str(hostile.value)
    assert "\r" not in message and "\n" not in message
    assert "‮" not in message

    # a legitimate name is untouched
    assert plugins.get_plugin("claude-code").name == "claude-code"
