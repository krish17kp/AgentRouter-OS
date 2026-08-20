"""Exact-value tests for the four plugin decisions that can destroy a file.

`scripts/run_mutation_ci.py` mutates `_safe_relative`, `_is_link_or_reparse`,
`_entry_matches` and `_remove_owned_empty_directory`, because those are the
functions that decide whether a path is safe to write through and whether
something is ours to delete. The adversarial suite proves the *behaviours*; this
file pins the *decisions*, so a mutation that flips one is caught rather than
surviving.

Assertions here are deliberately exact — a specific return value or a specific
refusal — because a mutant that changes a boundary while leaving the general
shape intact is precisely what a loose assertion misses.
"""

from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

import pytest

from agentrouter import plugins

# --- _safe_relative: the gate between a manifest and an arbitrary write -------


@pytest.mark.parametrize(
    "value",
    [
        "",  # empty
        "a\x00b",  # embedded NUL
        "..",  # traversal
        "a/../b",  # traversal mid-path
        "./a",  # dot component
        "/absolute.md",  # absolute
        "//server/share",  # UNC
        "C:/windows",  # drive letter
        "c:relative",  # drive-relative
        "a//b",  # empty component
        "trailing ",  # trailing space (Windows strips it)
        "trailing.",  # trailing dot (Windows strips it)
        "dir/trailing ",  # trailing space on a later component
        "CON",  # Windows reserved device
        "con.md",  # reserved with extension
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "LPT1",
        "com9.txt",
        "nul.txt.md",  # Windows treats `nul.anything` as the NUL device
        "a<b",  # characters Windows forbids
        "a>b",
        'a"b',
        "a|b",
        "a?b",
        "a*b",
        "a:b",
        "a\x01b",  # control character
        "a\x1fb",
    ],
)
def test_unsafe_relative_paths_are_rejected(value):
    """Every one of these is a way to escape the plugin root, or a name that
    Windows silently rewrites into a different file."""
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative(value, "plugin destination")


@pytest.mark.parametrize(
    ("value", "expected_parts"),
    [
        ("SKILL.md", ("SKILL.md",)),
        ("skills/agentrouter/SKILL.md", ("skills", "agentrouter", "SKILL.md")),
        ("a.b/c.d", ("a.b", "c.d")),
        ("CONSOLE.md", ("CONSOLE.md",)),  # not a reserved name, only a prefix of one
        ("COM10", ("COM10",)),  # only COM1-COM9 are reserved
    ],
)
def test_safe_relative_paths_are_accepted_with_their_exact_parts(value, expected_parts):
    """The rejections above must not be over-broad: these are legitimate names,
    and the returned path must be exactly the components given."""
    result = plugins._safe_relative(value, "plugin destination")
    assert result.parts == expected_parts


def test_backslashes_are_normalised_to_separators_not_kept_as_name_characters():
    """On Windows a backslash IS a separator, so treating it as an ordinary
    character would let `..\\..\\x` through as a single filename."""
    assert plugins._safe_relative("a\\b\\c.md", "d").parts == ("a", "b", "c.md")
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative("..\\escape.md", "d")


def test_nul_reserved_check_is_case_insensitive():
    for name in ("nul", "Nul", "NUL", "nUl"):
        with pytest.raises(plugins.PluginError):
            plugins._safe_relative(name, "d")


# --- _is_link_or_reparse: the gate before any write --------------------------


def test_a_plain_file_is_not_a_link(tmp_path):
    target = tmp_path / "plain.txt"
    target.write_text("x", encoding="utf-8")
    assert plugins._is_link_or_reparse(target) is False


def test_a_missing_path_is_not_a_link(tmp_path):
    """FileNotFoundError must return False, not propagate — the caller uses this
    to decide whether a destination is safe, and 'absent' is safe."""
    assert plugins._is_link_or_reparse(tmp_path / "nope") is False


def test_a_symlink_is_a_link(tmp_path):
    target = tmp_path / "t"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "l"
    link.symlink_to(target)
    assert plugins._is_link_or_reparse(link) is True


def test_a_dangling_symlink_is_still_a_link(tmp_path):
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "never-existed")
    assert plugins._is_link_or_reparse(link) is True


def test_a_junction_is_a_link_even_when_it_is_not_a_symlink(tmp_path, monkeypatch):
    """`os.path.isjunction` is the Windows-only branch. Simulated here so the
    decision is pinned on every platform; the real NTFS behaviour is a separate
    question (see test_plugins_platform.py)."""
    plain = tmp_path / "plain.txt"
    plain.write_text("x", encoding="utf-8")
    monkeypatch.setattr(os.path, "isjunction", lambda p: True, raising=False)
    assert plugins._is_link_or_reparse(plain) is True


def test_a_reparse_point_attribute_is_a_link(tmp_path, monkeypatch):
    """The `st_file_attributes` branch, simulated. Windows sets this bit for
    reparse points that are neither symlinks nor junctions."""
    plain = tmp_path / "plain.txt"
    plain.write_text("x", encoding="utf-8")
    monkeypatch.setattr(os.path, "isjunction", lambda p: False, raising=False)
    monkeypatch.setattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400, raising=False)

    real_lstat = Path.lstat
    genuine = real_lstat(plain)

    class Attrs:
        """A real stat result plus the Windows-only attribute bit."""

        st_mode = genuine.st_mode
        st_dev = genuine.st_dev
        st_ino = genuine.st_ino
        st_file_attributes = 0x400

    monkeypatch.setattr(Path, "lstat", lambda self: Attrs() if self == plain else real_lstat(self))
    assert plugins._is_link_or_reparse(plain) is True


# --- _entry_matches: is this file still the one we installed? -----------------


def _install(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    plugin = plugins.get_plugin("claude-code")
    plugins.install(plugin)
    root = plugins.dest_root(plugin)
    state, _ = plugins._load_state(root, plugin)
    entry = state["files"][plugin.files[0].dest]
    return plugin, plugins._safe_dest(root, plugin.files[0].dest), entry


def test_entry_matches_is_true_only_for_the_exact_installed_file(tmp_path, monkeypatch):
    _, dest, entry = _install(tmp_path, monkeypatch)
    assert plugins._entry_matches(dest, entry) is True


def test_entry_matches_is_false_when_the_content_changed(tmp_path, monkeypatch):
    _, dest, entry = _install(tmp_path, monkeypatch)
    dest.write_text("edited by the user", encoding="utf-8")
    assert plugins._entry_matches(dest, entry) is False


def test_entry_matches_is_false_when_the_digest_is_right_but_the_inode_is_not(
    tmp_path, monkeypatch
):
    """Digest equality alone must never be sufficient: an attacker can produce a
    file with our content at our path and it is still not the file we wrote."""
    _, dest, entry = _install(tmp_path, monkeypatch)
    payload = dest.read_bytes()
    replacement = dest.parent / "replacement"
    replacement.write_bytes(payload)
    os.replace(replacement, dest)  # same bytes, different inode

    assert plugins._sha256(dest.read_bytes()) == entry["installed_sha256"]
    assert plugins._entry_matches(dest, entry) is False


def test_entry_matches_is_false_for_a_missing_file(tmp_path, monkeypatch):
    _, dest, entry = _install(tmp_path, monkeypatch)
    dest.unlink()
    assert plugins._entry_matches(dest, entry) is False


def test_entry_matches_checks_the_backup_fields_when_asked(tmp_path, monkeypatch):
    """Backup and installed entries are different keys; comparing the wrong pair
    would let a restore overwrite something it should not."""
    _, dest, entry = _install(tmp_path, monkeypatch)
    assert plugins._entry_matches(dest, entry, backup=True) is False


# --- _remove_owned_empty_directory: the only directory deletion ---------------


def _owned_dir(tmp_path):
    directory = tmp_path / "owned"
    directory.mkdir()
    identity = plugins._identity_json(directory.lstat())
    return directory, identity


def test_an_absent_directory_reports_absent(tmp_path):
    missing = tmp_path / "gone"
    assert plugins._remove_owned_empty_directory(tmp_path, missing, [0, 0]) == "absent"


def test_an_owned_empty_directory_is_removed(tmp_path):
    directory, identity = _owned_dir(tmp_path)
    assert plugins._remove_owned_empty_directory(tmp_path, directory, identity) == (
        "removed (empty directory)"
    )
    assert not directory.exists()


def test_a_directory_with_different_identity_is_preserved(tmp_path):
    """If the directory at that path is not the one we created, it is not ours."""
    directory, _ = _owned_dir(tmp_path)
    result = plugins._remove_owned_empty_directory(tmp_path, directory, [999999, 999999])
    assert result == "preserved (directory identity changed)"
    assert directory.exists()


def test_a_non_empty_directory_is_preserved(tmp_path):
    """The invariant that matters most: never recursively delete a tree."""
    directory, identity = _owned_dir(tmp_path)
    (directory / "user-file.txt").write_text("mine", encoding="utf-8")

    result = plugins._remove_owned_empty_directory(tmp_path, directory, identity)

    assert result == "preserved (not empty)"
    assert (directory / "user-file.txt").read_text(encoding="utf-8") == "mine"


def test_a_directory_containing_only_a_dotfile_is_still_not_empty(tmp_path):
    """`iterdir` includes dotfiles; a check that skipped them would delete a
    directory holding someone's `.config`."""
    directory, identity = _owned_dir(tmp_path)
    (directory / ".hidden").write_text("mine", encoding="utf-8")

    assert plugins._remove_owned_empty_directory(tmp_path, directory, identity) == (
        "preserved (not empty)"
    )
    assert (directory / ".hidden").exists()


def test_a_directory_containing_only_a_subdirectory_is_not_empty(tmp_path):
    directory, identity = _owned_dir(tmp_path)
    (directory / "sub").mkdir()

    assert plugins._remove_owned_empty_directory(tmp_path, directory, identity) == (
        "preserved (not empty)"
    )
    assert (directory / "sub").exists()


def test_a_symlinked_directory_is_refused_rather_than_removed(tmp_path):
    """Removing through a link would delete the target, not our directory."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(plugins.PluginError):
        plugins._remove_owned_empty_directory(tmp_path, link, plugins._identity_json(real.lstat()))
    assert real.exists()


def test_a_file_where_a_directory_is_expected_is_refused(tmp_path):
    not_a_directory = tmp_path / "actually-a-file"
    not_a_directory.write_text("x", encoding="utf-8")

    with pytest.raises(plugins.PluginError):
        plugins._remove_owned_empty_directory(tmp_path, not_a_directory, [0, 0])
    assert not_a_directory.exists()


def test_the_staging_name_is_unique_per_attempt(tmp_path, monkeypatch):
    """Two removals must not collide on the staging path."""
    seen = []
    real_uuid4 = uuid.uuid4

    def record():
        value = real_uuid4()
        seen.append(value.hex)
        return value

    monkeypatch.setattr(plugins.uuid, "uuid4", record)
    for name in ("a", "b"):
        directory = tmp_path / name
        directory.mkdir()
        plugins._remove_owned_empty_directory(
            tmp_path, directory, plugins._identity_json(directory.lstat())
        )
    assert len(set(seen)) == len(seen) == 2


def test_entry_matches_is_false_when_the_file_cannot_be_verified(tmp_path, monkeypatch):
    """The dangerous direction. If verification failure meant "matches", an
    unreadable file would count as ours and become eligible for deletion — the
    exact opposite of failing closed.
    """
    _, dest, entry = _install(tmp_path, monkeypatch)

    def unreadable(*_args, **_kwargs):
        raise plugins.PluginError("cannot verify")

    monkeypatch.setattr(plugins, "_read_verified", unreadable)
    assert plugins._entry_matches(dest, entry) is False
    assert plugins._entry_matches(dest, entry, backup=True) is False


def test_a_verification_failure_names_what_it_was_reading(tmp_path, monkeypatch):
    """The label distinguishes "managed plugin file" from "plugin backup" in
    errors. A wrong or empty label sends someone to inspect the wrong file."""
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path))
    plugin = plugins.get_plugin("claude-code")
    plugins.install(plugin)
    dest = plugins._safe_dest(plugins.dest_root(plugin), plugin.files[0].dest)

    victim = tmp_path / "outside"
    victim.write_text("x", encoding="utf-8")
    dest.unlink()
    dest.symlink_to(victim)

    with pytest.raises(plugins.PluginError) as exc:
        plugins._read_verified(dest, "managed plugin file")
    assert "managed plugin file" in str(exc.value)

    with pytest.raises(plugins.PluginError) as backup_exc:
        plugins._read_verified(dest, "plugin backup")
    assert "plugin backup" in str(backup_exc.value)


def test_an_unsafe_relative_path_error_names_the_label_and_the_value():
    """Both halves are load-bearing: the label says which field was wrong, and
    the repr says what was actually supplied."""
    with pytest.raises(plugins.PluginError) as exc:
        plugins._safe_relative("../escape.md", "plugin destination")
    message = str(exc.value)
    assert "plugin destination" in message
    assert "../escape.md" in message


def test_directory_removal_outcomes_are_the_exact_documented_strings(tmp_path):
    """Callers and the doctor branch on these strings, so they are an interface
    rather than prose."""
    missing = tmp_path / "missing"
    assert plugins._remove_owned_empty_directory(tmp_path, missing, [0, 0]) == "absent"

    wrong = tmp_path / "wrong"
    wrong.mkdir()
    assert plugins._remove_owned_empty_directory(tmp_path, wrong, [1, 1]) == (
        "preserved (directory identity changed)"
    )

    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x", encoding="utf-8")
    assert (
        plugins._remove_owned_empty_directory(tmp_path, full, plugins._identity_json(full.lstat()))
        == "preserved (not empty)"
    )

    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        plugins._remove_owned_empty_directory(
            tmp_path, empty, plugins._identity_json(empty.lstat())
        )
        == "removed (empty directory)"
    )


@pytest.mark.parametrize(
    ("value", "expected_parts"),
    [
        # An internal space is legal on every platform this targets. Only a
        # TRAILING space is a problem (Windows strips it), so the boundary is
        # `ord(char) < 32` and not `<= 32`.
        ("my file.md", ("my file.md",)),
        ("skills/my agent/SKILL.md", ("skills", "my agent", "SKILL.md")),
        # Letters that appear in the forbidden-character set's own spelling must
        # not themselves become forbidden.
        ("XRAY.md", ("XRAY.md",)),
        ("aXbXc.md", ("aXbXc.md",)),
        # Characters adjacent to the control-character boundary.
        ("!bang.md", ("!bang.md",)),
        ("~tilde.md", ("~tilde.md",)),
    ],
)
def test_legitimate_names_near_the_rejection_boundaries_are_accepted(value, expected_parts):
    """The rejection rules must not be one character too wide.

    Each of these sits immediately next to a boundary the validator draws, so a
    mutation that widens the boundary by one turns a legal filename into an
    error the user cannot work around.
    """
    assert plugins._safe_relative(value, "plugin destination").parts == expected_parts


def test_a_trailing_space_is_rejected_while_an_internal_one_is_not():
    """The two cases the space boundary has to separate."""
    # Internal spaces are fine, including one before the extension: the rule is
    # about the component's LAST character, because that is what Windows strips.
    assert plugins._safe_relative("a b.md", "d").parts == ("a b.md",)
    assert plugins._safe_relative("ab .md", "d").parts == ("ab .md",)

    with pytest.raises(plugins.PluginError):
        plugins._safe_relative("ab ", "d")  # component ends with a space
    with pytest.raises(plugins.PluginError):
        plugins._safe_relative("dir /file.md", "d")  # a component ends with one


def test_directory_verification_failures_name_the_directory_being_checked(tmp_path):
    """`_directory_lstat`'s label is what tells the user which directory failed —
    the managed one, or the staged copy mid-removal."""
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x", encoding="utf-8")

    with pytest.raises(plugins.PluginError) as managed:
        plugins._directory_lstat(not_a_directory, "managed plugin directory")
    # The label is a PREFIX of the message, so assert exactly that. A substring
    # check is useless: "XXmanaged plugin directoryXX" contains the real label.
    assert str(managed.value).startswith("managed plugin directory is not a safe directory:")

    with pytest.raises(plugins.PluginError) as staged:
        plugins._directory_lstat(not_a_directory, "staged managed plugin directory")
    assert str(staged.value).startswith("staged managed plugin directory is not a safe directory:")


def test_a_symlinked_directory_error_names_the_managed_label(tmp_path):
    """The label travels through the whole removal path, so it is asserted where
    a real caller would see it."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(plugins.PluginError) as exc:
        plugins._remove_owned_empty_directory(tmp_path, link, plugins._identity_json(real.lstat()))
    assert str(exc.value).startswith("managed plugin directory is not a safe directory:")


@pytest.mark.parametrize("value", ["", "a\x00b"])
def test_the_empty_and_nul_rejection_carries_its_own_message(value):
    """`_safe_relative` raises in two places. This is the FIRST, reachable only
    by an empty value or one containing a NUL — a test using `../escape.md`
    exercises the second raise and leaves this message unchecked.
    """
    with pytest.raises(plugins.PluginError) as exc:
        plugins._safe_relative(value, "plugin destination")
    message = str(exc.value)
    assert message.startswith("unsafe relative path for plugin destination:")
    assert repr(value) in message


def test_the_traversal_rejection_message_is_exact():
    with pytest.raises(plugins.PluginError) as exc:
        plugins._safe_relative("../escape.md", "plugin destination")
    assert str(exc.value) == "unsafe relative path for plugin destination: '../escape.md'"


# --- the concurrent-change recovery path -------------------------------------
#
# Between `os.rename(directory, staged)` and the removal, another process can
# swap what sits at the staged path. That window is where data loss would happen,
# so it is reached deliberately here rather than left to chance.


def test_a_staged_directory_replaced_by_a_file_is_refused_and_restored(tmp_path, monkeypatch):
    """After staging, the path must still be the directory we staged. If it is
    not, removal is abandoned rather than applied to whatever is now there."""
    directory = tmp_path / "owned"
    directory.mkdir()
    identity = plugins._identity_json(directory.lstat())

    real_rename = os.rename

    swapped = []

    def rename_then_swap(src, dst):
        real_rename(src, dst)
        if not swapped:  # one-shot, so recovery can still use the real rename
            swapped.append(True)
            # Simulate a racing process replacing the staged directory with a file.
            Path(dst).rmdir()
            Path(dst).write_text("planted", encoding="utf-8")

    monkeypatch.setattr(plugins.os, "rename", rename_then_swap)

    with pytest.raises(plugins.PluginError) as exc:
        plugins._remove_owned_empty_directory(tmp_path, directory, identity)
    assert str(exc.value).startswith("staged managed plugin directory is not a safe directory:")


def test_a_staged_directory_whose_identity_changed_is_restored_not_removed(tmp_path, monkeypatch):
    """The identity re-check after staging: a different directory object at the
    staged path means ours is gone, so put things back and report it."""
    directory = tmp_path / "owned"
    directory.mkdir()
    identity = plugins._identity_json(directory.lstat())

    real_rename = os.rename

    # Made in advance so it is genuinely a different inode: rmdir+mkdir at the
    # same path frequently reuses the inode number, which would leave the
    # identity unchanged and test nothing.
    impostor = tmp_path / "impostor"
    impostor.mkdir()

    swapped = []

    def rename_then_replace(src, dst):
        # One-shot: the recovery path calls os.rename again to restore, and that
        # call must use the real implementation or the test tests itself.
        real_rename(src, dst)
        if not swapped:
            swapped.append(True)
            Path(dst).rmdir()
            real_rename(impostor, dst)

    monkeypatch.setattr(plugins.os, "rename", rename_then_replace)

    result = plugins._remove_owned_empty_directory(tmp_path, directory, identity)
    assert result == "preserved (directory changed concurrently)"
    assert directory.exists(), "the directory was not restored after the abort"


def test_a_rename_failure_is_reported_with_the_directory_it_could_not_remove(tmp_path, monkeypatch):
    """An OSError here must become a typed error naming the directory, not a
    bare OSError reaching the CLI."""
    directory = tmp_path / "owned"
    directory.mkdir()
    identity = plugins._identity_json(directory.lstat())

    def refuse(src, dst):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(plugins.os, "rename", refuse)

    with pytest.raises(plugins.PluginError) as exc:
        plugins._remove_owned_empty_directory(tmp_path, directory, identity)
    message = str(exc.value)
    assert message.startswith("could not remove empty managed directory")
    assert str(directory) in message
    assert directory.exists(), "the directory was lost when removal failed"
