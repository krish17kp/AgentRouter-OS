"""Phase P8 — plugin/skill installer (reversible, idempotent, safe)."""

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentrouter import plugins
from agentrouter.cli import app

runner = CliRunner()


@pytest.fixture
def plug_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    return tmp_path


def _dest(p, tmp_path):
    return tmp_path / p.name / p.files[0].dest


def test_install_creates_file(plug_root):
    p = plugins.get_plugin("claude-code")
    results = plugins.install(p)
    dest = _dest(p, plug_root)
    assert dest.exists()
    assert plugins.status(p) == "installed"
    assert results[0]["result"] == "created"


def test_install_is_idempotent(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    second = plugins.install(p)
    assert "skipped" in second[0]["result"]


def test_install_refuses_to_clobber_without_force(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("USER CONTENT", encoding="utf-8")
    with pytest.raises(plugins.PluginError):
        plugins.install(p)
    assert dest.read_text(encoding="utf-8") == "USER CONTENT"  # untouched


def test_force_backs_up_then_uninstall_restores(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("USER CONTENT", encoding="utf-8")
    plugins.install(p, force=True)
    assert dest.read_text(encoding="utf-8") != "USER CONTENT"  # replaced
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    assert backup.exists()
    plugins.uninstall(p)
    assert dest.read_text(encoding="utf-8") == "USER CONTENT"  # restored
    assert not backup.exists()


def test_uninstall_removes_created_file(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    plugins.uninstall(p)
    assert not _dest(p, plug_root).exists()
    assert plugins.status(p) == "not-installed"


def test_uninstall_removes_only_empty_integration_directory(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    dest = _dest(p, plug_root)
    integration_dir = dest.parent
    parent = integration_dir.parent

    results = plugins.uninstall(p)

    assert not integration_dir.exists()
    assert parent.is_dir()  # never climb into or remove the non-plugin parent
    assert any(r.get("kind") == "directory" and "removed" in r["result"] for r in results)


def test_uninstall_preserves_unrelated_file_and_non_empty_directory(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    dest = _dest(p, plug_root)
    unrelated = dest.parent / "NOTES.md"
    unrelated.write_text("user notes", encoding="utf-8")

    plugins.uninstall(p)

    assert not dest.exists()
    assert unrelated.read_text(encoding="utf-8") == "user notes"
    assert dest.parent.is_dir()


def test_uninstall_preserves_post_install_user_edits(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    dest = _dest(p, plug_root)
    dest.write_text("USER CHANGED THIS", encoding="utf-8")

    results = plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "USER CHANGED THIS"
    assert "preserved" in results[0]["result"]


def test_uninstall_is_idempotent_and_reinstall_works(plug_root):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    plugins.uninstall(p)
    second = plugins.uninstall(p)
    assert all(r["result"] == "absent" for r in second)

    installed = plugins.install(p)
    assert installed[0]["result"] == "created"
    assert _dest(p, plug_root).is_file()


def test_uninstall_restores_backup_when_managed_file_was_removed(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    plugins.install(p, force=True)
    dest.unlink()

    plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert not dest.with_name(dest.name + plugins._BAK_SUFFIX).exists()


def test_uninstall_preserves_later_edit_and_backup(plug_root):
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    plugins.install(p, force=True)
    dest.write_text("LATER USER EDIT", encoding="utf-8")

    results = plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "LATER USER EDIT"
    assert dest.with_name(dest.name + plugins._BAK_SUFFIX).read_text(encoding="utf-8") == (
        "ORIGINAL USER FILE"
    )
    assert "preserved" in results[0]["result"]


def test_uninstall_preserves_identical_file_that_was_never_installed(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plugins._src_bytes(p.files[0].src))

    results = plugins.uninstall(p)

    assert dest.is_file()
    assert results[0]["result"] == "preserved (unmanaged)"


def test_uninstall_uses_recorded_digest_after_packaged_payload_changes(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    plugins.install(p)
    dest = _dest(p, plug_root)
    old_payload = dest.read_bytes()
    original = plugins._src_bytes

    def updated_payload(relative):
        if relative == p.files[0].src:
            return b"a future packaged payload\n"
        return original(relative)

    monkeypatch.setattr(plugins, "_src_bytes", updated_payload)
    results = plugins.uninstall(p)

    assert old_payload != updated_payload(p.files[0].src)
    assert not dest.exists()
    assert results[0]["result"] == "removed"


def test_force_install_refuses_hard_link_without_changing_outside_file(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    outside = plug_root / "outside-user-file.md"
    outside.write_text("DO NOT TOUCH", encoding="utf-8")
    try:
        os.link(outside, dest)
    except OSError as exc:
        pytest.skip(f"hard-link creation unavailable: {exc}")

    with pytest.raises(plugins.PluginError, match="hard links"):
        plugins.install(p, force=True)

    assert outside.read_text(encoding="utf-8") == "DO NOT TOUCH"
    assert os.path.samefile(outside, dest)


def test_backup_collision_created_during_link_is_never_overwritten(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("USER CONTENT", encoding="utf-8")
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    outside = plug_root / "outside-backup-target.md"
    outside.write_text("DO NOT TOUCH", encoding="utf-8")
    original_link = os.link

    def racing_link(src, target, *args, **kwargs):
        if target == backup and not backup.exists():
            original_link(outside, backup)
        return original_link(src, target, *args, **kwargs)

    monkeypatch.setattr(plugins.os, "link", racing_link)
    with pytest.raises(plugins.PluginError, match="backup appeared"):
        plugins.install(p, force=True)

    assert dest.read_text(encoding="utf-8") == "USER CONTENT"
    assert outside.read_text(encoding="utf-8") == "DO NOT TOUCH"


def test_edit_racing_uninstall_is_preserved(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    plugins.install(p)
    dest = _dest(p, plug_root)
    original_stage = plugins._stage_exact
    changed = False

    def edit_then_stage(root, path, digest, identity, label):
        nonlocal changed
        if path == dest and not changed:
            changed = True
            path.write_text("CONCURRENT USER EDIT", encoding="utf-8")
        return original_stage(root, path, digest, identity, label)

    monkeypatch.setattr(plugins, "_stage_exact", edit_then_stage)
    results = plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "CONCURRENT USER EDIT"
    assert "preserved" in results[0]["result"]


def test_restore_failure_rolls_managed_file_back_into_place(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    plugins.install(p, force=True)
    managed_payload = dest.read_bytes()

    def fail_restore(root, backup, destination):
        raise plugins.PluginError("simulated restore failure")

    monkeypatch.setattr(plugins, "_restore_backup", fail_restore)
    with pytest.raises(plugins.PluginError, match="simulated restore failure"):
        plugins.uninstall(p)

    assert dest.read_bytes() == managed_payload
    assert dest.with_name(dest.name + plugins._BAK_SUFFIX).is_file()


def test_backup_preserves_original_file_identity_and_mode(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("PRIVATE USER CONTENT", encoding="utf-8")
    dest.chmod(0o600)
    original = dest.stat()

    plugins.install(p, force=True)
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)

    assert backup.stat().st_ino == original.st_ino
    assert backup.stat().st_mode == original.st_mode


def test_post_replace_verification_failure_keeps_recoverable_backup(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    original_lstat = plugins._regular_lstat

    def fail_after_replace(path, label, **kwargs):
        if label == "new AgentRouter-managed file" and path == dest:
            raise plugins.PluginError("simulated post-replace verification failure")
        return original_lstat(path, label, **kwargs)

    monkeypatch.setattr(plugins, "_regular_lstat", fail_after_replace)
    with pytest.raises(plugins.PluginError, match="backup and journal were preserved"):
        plugins.install(p, force=True)
    monkeypatch.setattr(plugins, "_regular_lstat", original_lstat)

    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    assert backup.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert plugins._transaction_path(plugins.dest_root(p), p).is_file()

    plugins.uninstall(p)
    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert not backup.exists()


def test_state_save_failure_preserves_concurrent_edit_backup_and_journal(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    original_save = plugins._save_state

    def edit_then_fail(root, plugin, state):
        entry = state["files"].get(p.files[0].dest)
        if entry and entry["disposition"] == "replaced":
            dest.write_text("CONCURRENT USER EDIT", encoding="utf-8")
            raise plugins.PluginError("simulated state failure")
        return original_save(root, plugin, state)

    monkeypatch.setattr(plugins, "_save_state", edit_then_fail)
    with pytest.raises(plugins.PluginError, match="preserved a concurrent edit"):
        plugins.install(p, force=True)

    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    assert dest.read_text(encoding="utf-8") == "CONCURRENT USER EDIT"
    assert backup.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert plugins._transaction_path(plugins.dest_root(p), p).is_file()


def test_interrupted_forced_install_is_recovered_on_uninstall(plug_root):
    p = plugins.get_plugin("codex")
    root = plugins.dest_root(p)
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    original, original_info = plugins._read_verified(dest, "test destination")
    backup = plugins._backup_path(root, dest)
    want = plugins._src_bytes(p.files[0].src)
    transaction = {
        "schema": 1,
        "plugin": p.name,
        "phase": "prepared",
        "dest": p.files[0].dest,
        "backup": backup.relative_to(root).as_posix(),
        "original_sha256": plugins._sha256(original),
        "original_identity": plugins._identity_json(original_info),
        "original_mode": original_info.st_mode & 0o7777,
        "installed_sha256": plugins._sha256(want),
    }
    plugins._write_transaction(root, p, transaction)
    plugins._create_backup(root, dest, backup)
    transaction["phase"] = "backed_up"
    plugins._write_transaction(root, p, transaction)
    plugins._atomic_replace_bytes(root, dest, want)

    plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert not backup.exists()
    assert not plugins._transaction_path(root, p).exists()


def test_prepared_journal_never_claims_a_concurrent_backup(plug_root):
    p = plugins.get_plugin("codex")
    root = plugins.dest_root(p)
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    original, original_info = plugins._read_verified(dest, "test destination")
    backup = plugins._backup_path(root, dest)
    transaction = {
        "schema": 1,
        "plugin": p.name,
        "phase": "prepared",
        "dest": p.files[0].dest,
        "backup": backup.relative_to(root).as_posix(),
        "original_sha256": plugins._sha256(original),
        "original_identity": plugins._identity_json(original_info),
        "original_mode": original_info.st_mode & 0o7777,
        "installed_sha256": plugins._sha256(plugins._src_bytes(p.files[0].src)),
    }
    plugins._write_transaction(root, p, transaction)
    backup.write_text("CONCURRENT ACTOR BACKUP", encoding="utf-8")

    plugins.uninstall(p)

    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert backup.read_text(encoding="utf-8") == "CONCURRENT ACTOR BACKUP"
    assert not plugins._transaction_path(root, p).exists()


def test_backup_creation_failure_removes_only_prepared_journal(plug_root, monkeypatch):
    p = plugins.get_plugin("codex")
    root = plugins.dest_root(p)
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    backup = plugins._backup_path(root, dest)

    def concurrent_backup(_root, _dest, backup_path):
        backup_path.write_text("CONCURRENT ACTOR BACKUP", encoding="utf-8")
        raise plugins.PluginError("simulated concurrent backup")

    monkeypatch.setattr(plugins, "_create_backup", concurrent_backup)
    with pytest.raises(plugins.PluginError, match="simulated concurrent backup"):
        plugins.install(p, force=True)

    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert backup.read_text(encoding="utf-8") == "CONCURRENT ACTOR BACKUP"
    assert not plugins._transaction_path(root, p).exists()


def test_interrupted_uninstall_recognizes_completed_backup_restore(plug_root):
    p = plugins.get_plugin("codex")
    root = plugins.dest_root(p)
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    plugins.install(p, force=True)
    state, _ = plugins._load_state(root, p)
    entry = state["files"][p.files[0].dest]
    backup = plugins._safe_dest(root, entry["backup"], "test backup")
    staged = plugins._stage_exact(
        root,
        dest,
        entry["installed_sha256"],
        entry["installed_identity"],
        "test managed plugin file",
    )
    assert staged is not None
    plugins._restore_backup(root, backup, dest)
    staged.unlink()

    results = plugins.uninstall(p)

    assert results[0]["result"] == "recovered completed backup restoration"
    assert dest.read_text(encoding="utf-8") == "ORIGINAL USER FILE"
    assert not plugins._state_path(root, p).exists()


def test_registry_rename_uninstalls_historical_managed_path(plug_root):
    old = plugins.Plugin(
        name="migration-test",
        description="old",
        files=(plugins.PluginFile("codex/AGENTS.md", "old.md"),),
        _home_subdir=".unused",
    )
    new = plugins.Plugin(
        name="migration-test",
        description="new",
        files=(plugins.PluginFile("codex/AGENTS.md", "new.md"),),
        _home_subdir=".unused",
    )
    plugins.install(old)
    old_dest = plug_root / old.name / "old.md"

    results = plugins.uninstall(new)

    assert not old_dest.exists()
    assert any(result["dest"].endswith("old.md") for result in results)


def test_replaced_backup_with_same_content_but_new_identity_is_not_restored(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ORIGINAL USER FILE", encoding="utf-8")
    plugins.install(p, force=True)
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    content = backup.read_bytes()
    replacement = backup.with_name("replacement.tmp")
    replacement.write_bytes(content)
    os.replace(replacement, backup)

    results = plugins.uninstall(p)

    assert "ambiguous" in results[0]["result"]
    assert dest.is_file()
    assert backup.is_file()


def test_roundtrip_removes_empty_private_state_directory(plug_root):
    p = plugins.get_plugin("codex")
    plugins.install(p)
    state_dir = plugins._state_path(plugins.dest_root(p), p).parent
    assert state_dir.is_dir()

    plugins.uninstall(p)

    assert not state_dir.exists()


def test_explicit_adoption_allows_legacy_identical_file_cleanup(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plugins._src_bytes(p.files[0].src))

    result = plugins.install(p, adopt_identical=True)
    plugins.uninstall(p)

    assert "adopted" in result[0]["result"]
    assert not dest.exists()


def test_directory_identity_swap_is_preserved_not_removed(plug_root, monkeypatch):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    directory = _dest(p, plug_root).parent
    outside = plug_root / "outside-empty-directory"
    outside.mkdir()
    original_rename = os.rename
    redirected = False

    def redirect_directory_rename(src, target, *args, **kwargs):
        nonlocal redirected
        if Path(src) == directory and not redirected:
            redirected = True
            return original_rename(outside, target, *args, **kwargs)
        return original_rename(src, target, *args, **kwargs)

    monkeypatch.setattr(plugins.os, "rename", redirect_directory_rename)
    with pytest.raises(plugins.PluginError, match="directory changed concurrently"):
        plugins.uninstall(p)

    assert directory.is_dir()
    assert list(directory.parent.glob(".agentrouter.agentrouter-remove-*"))


def test_final_directory_path_swap_is_never_deleted(plug_root, monkeypatch):
    p = plugins.get_plugin("claude-code")
    plugins.install(p)
    directory = _dest(p, plug_root).parent
    original_remove = plugins._remove_directory_by_handle
    displaced: Path | None = None

    def swap_before_handle_remove(staged, identity):
        nonlocal displaced
        displaced = staged.with_name(f"{staged.name}-displaced")
        os.rename(staged, displaced)
        staged.mkdir()
        return original_remove(staged, identity)

    monkeypatch.setattr(plugins, "_remove_directory_by_handle", swap_before_handle_remove)
    with pytest.raises(plugins.PluginError, match="staged directory changed"):
        plugins.uninstall(p)

    assert displaced is not None and displaced.is_dir()
    replacement = displaced.with_name(displaced.name.removesuffix("-displaced"))
    assert replacement.is_dir()
    assert not directory.exists()


@pytest.mark.parametrize(
    "bad_dest",
    [
        ".",
        "../escape.md",
        "..\\escape.md",
        "/tmp/escape.md",
        "C:\\escape.md",
        "CON",
        "file:stream",
        "trailing. ",
    ],
)
def test_plugin_destination_traversal_is_rejected(plug_root, bad_dest):
    p = plugins.Plugin(
        name="malicious",
        description="test",
        files=(plugins.PluginFile("codex/AGENTS.md", bad_dest),),
        _home_subdir=".unused",
    )

    with pytest.raises(plugins.PluginError, match="unsafe relative path"):
        plugins.install(p)
    with pytest.raises(plugins.PluginError, match="unsafe relative path"):
        plugins.uninstall(p)
    assert not (plug_root / "escape.md").exists()


def test_symlink_destination_is_rejected_without_touching_target(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    outside = plug_root / "outside-user-file.md"
    outside.write_text("DO NOT TOUCH", encoding="utf-8")
    try:
        dest.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(p, force=True)
    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.uninstall(p)
    assert outside.read_text(encoding="utf-8") == "DO NOT TOUCH"
    assert dest.is_symlink()


def test_reparse_component_is_rejected(monkeypatch, plug_root):
    """Covers Windows junction/reparse handling without requiring junction privileges."""
    p = plugins.get_plugin("claude-code")
    dest = _dest(p, plug_root)
    original = plugins._is_link_or_reparse

    def fake_reparse(path):
        return path == dest.parent or original(path)

    monkeypatch.setattr(plugins, "_is_link_or_reparse", fake_reparse)
    with pytest.raises(plugins.PluginError, match="link or reparse point"):
        plugins.install(p)


def test_cleanup_directory_traversal_is_rejected(plug_root):
    p = plugins.Plugin(
        name="malicious",
        description="test",
        files=(plugins.PluginFile("codex/AGENTS.md", "AGENTS.md"),),
        _home_subdir=".unused",
        cleanup_dirs=("../outside",),
    )

    with pytest.raises(plugins.PluginError, match="unsafe relative path"):
        plugins.uninstall(p)


def test_force_install_refuses_existing_backup(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("CURRENT USER FILE", encoding="utf-8")
    backup = dest.with_name(dest.name + plugins._BAK_SUFFIX)
    backup.write_text("OLDER BACKUP", encoding="utf-8")

    with pytest.raises(plugins.PluginError, match="backup already exists"):
        plugins.install(p, force=True)
    assert dest.read_text(encoding="utf-8") == "CURRENT USER FILE"
    assert backup.read_text(encoding="utf-8") == "OLDER BACKUP"
    assert not plugins._transaction_path(plugins.dest_root(p), p).exists()


def test_plan_changes_nothing(plug_root):
    p = plugins.get_plugin("codex")
    plan = plugins.plan(p)
    assert plan[0]["action"] == "create"
    assert not _dest(p, plug_root).exists()  # plan is read-only


def test_cli_dry_run_reports_explicit_identical_adoption(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plugins._src_bytes(p.files[0].src))

    result = runner.invoke(app, ["plugin", "install", "codex", "--dry-run", "--adopt-identical"])

    assert result.exit_code == 0, result.output
    assert "adopt identical legacy installation" in result.output
    assert not plugins._state_path(plugins.dest_root(p), p).exists()


def test_plan_distinguishes_recorded_preexisting_file_from_managed(plug_root):
    p = plugins.get_plugin("codex")
    dest = _dest(p, plug_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plugins._src_bytes(p.files[0].src))
    plugins.install(p)

    preserve_plan = plugins.plan(p)
    adoption_plan = plugins.plan(p, adopt_identical=True)

    assert preserve_plan[0]["action"] == "record pre-existing (preserved on uninstall)"
    assert adoption_plan[0]["action"] == "adopt identical legacy installation (managed)"


def test_unknown_plugin_raises():
    with pytest.raises(plugins.PluginError):
        plugins.get_plugin("does-not-exist")


# --- CLI wiring ---------------------------------------------------------------


def test_cli_install_and_uninstall_roundtrip(plug_root):
    r = runner.invoke(app, ["plugin", "install", "claude-code"])
    assert r.exit_code == 0, r.output
    assert "created" in r.output
    r2 = runner.invoke(app, ["plugin", "uninstall", "claude-code"])
    assert r2.exit_code == 0, r2.output
    assert "removed" in r2.output


def test_cli_unknown_plugin_is_usage_error(plug_root):
    r = runner.invoke(app, ["plugin", "install", "nope"])
    assert r.exit_code == 2, r.output


def test_cli_uninstall_reports_partial_results_before_error(plug_root, monkeypatch):
    partial = [{"kind": "file", "dest": "first", "result": "removed"}]

    def fail_uninstall(_plugin):
        raise plugins.PluginError("simulated late failure", results=partial)

    monkeypatch.setattr(plugins, "uninstall", fail_uninstall)
    result = runner.invoke(app, ["plugin", "uninstall", "codex"])

    assert result.exit_code == 1
    assert "removed" in result.output
    assert "first" in result.output
    assert "simulated late failure" in result.output
