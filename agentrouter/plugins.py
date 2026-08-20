"""Reversible installer for bundled host integrations.

The installer is deliberately conservative: it records ownership, writes by atomic
directory-entry replacement, refuses links/reparse points and ambiguous hard links,
and never recursively removes directories.  If ownership cannot be proven, uninstall
preserves the path and reports why.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath

_BAK_SUFFIX = ".agentrouter-bak"
_STATE_DIR = ".agentrouter-state"
_STATE_SCHEMA = 2
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class PluginFile:
    src: str
    dest: str


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    files: tuple[PluginFile, ...]
    _home_subdir: str
    cleanup_dirs: tuple[str, ...] = ()


PLUGINS: dict[str, Plugin] = {
    "claude-code": Plugin(
        name="claude-code",
        description="AgentRouter routing skill for Claude Code (~/.claude/skills/agentrouter/).",
        files=(PluginFile("claude-code/agentrouter/SKILL.md", "skills/agentrouter/SKILL.md"),),
        _home_subdir=".claude",
        cleanup_dirs=("skills/agentrouter",),
    ),
    "codex": Plugin(
        name="codex",
        description="AgentRouter AGENTS.md guidance for Codex (~/.codex/AGENTS.md).",
        files=(PluginFile("codex/AGENTS.md", "AGENTS.md"),),
        _home_subdir=".codex",
    ),
}


class PluginError(Exception):
    """Raised for an unknown plugin or a condition that cannot be changed safely."""

    def __init__(self, message: str, *, results: list[dict] | None = None):
        super().__init__(message)
        self.results = list(results or [])


def get_plugin(name: str) -> Plugin:
    try:
        return PLUGINS[name]
    except KeyError:
        raise PluginError(f"unknown plugin '{name}'. Known: {', '.join(sorted(PLUGINS))}") from None


def _safe_relative(value: str, label: str) -> Path:
    """Return a portable relative path, rejecting traversal and Windows aliases."""
    if not value or "\x00" in value:
        raise PluginError(f"unsafe relative path for {label}: {value!r}")
    normalized = value.replace("\\", "/")
    raw_parts = normalized.split("/")
    path = PurePosixPath(normalized)
    invalid_part = any(
        not part
        or part in {".", ".."}
        or part[-1:] in {" ", "."}
        or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        or part.split(".", 1)[0].upper() in _WINDOWS_RESERVED
        for part in raw_parts
    )
    if (
        invalid_part
        or path.is_absolute()
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise PluginError(f"unsafe relative path for {label}: {value!r}")
    return Path(*raw_parts)


def dest_root(p: Plugin) -> Path:
    override = os.environ.get("AGENTROUTER_PLUGIN_ROOT")
    if override:
        name = _safe_relative(p.name, "plugin name")
        if len(name.parts) != 1:
            raise PluginError(f"unsafe relative path for plugin name: {p.name!r}")
        return Path(override) / name
    return Path.home() / _safe_relative(p._home_subdir, "plugin home")


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is not None and is_junction(path):
        return True
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _assert_no_link_components(root: Path, candidate: Path) -> None:
    current = root
    if _is_link_or_reparse(current):
        raise PluginError(f"unsafe destination contains a link or reparse point: {current}")
    for part in candidate.relative_to(root).parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise PluginError(f"unsafe destination contains a link or reparse point: {current}")


def _safe_dest(root: Path, relative: str, label: str = "plugin destination") -> Path:
    rel = _safe_relative(relative, label)
    candidate = root / rel
    _assert_no_link_components(root, candidate)
    resolved_root = root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError:
        raise PluginError(f"unsafe relative path for {label}: {relative!r}") from None
    return candidate


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


def _identity_json(info: os.stat_result) -> list[int]:
    return [*_identity(info)]


def _regular_lstat(path: Path, label: str, *, single_link: bool = True) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise PluginError(f"{label} disappeared during the operation: {path}") from None
    if _is_link_or_reparse(path) or not stat.S_ISREG(info.st_mode):
        raise PluginError(f"{label} is not a regular non-link file; refusing to modify it: {path}")
    if single_link and info.st_nlink != 1:
        raise PluginError(f"{label} has {info.st_nlink} hard links; refusing to modify it: {path}")
    return info


def _directory_lstat(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise PluginError(f"{label} disappeared during the operation: {path}") from None
    if _is_link_or_reparse(path) or not stat.S_ISDIR(info.st_mode):
        raise PluginError(f"{label} is not a safe directory: {path}")
    return info


def _read_verified(
    path: Path, label: str, *, single_link: bool = True
) -> tuple[bytes, os.stat_result]:
    """Read a stable regular file without following a final-component symlink."""
    before = _regular_lstat(path, label, single_link=single_link)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PluginError(f"could not safely open {label} {path}: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if _identity(opened) != _identity(before) or not stat.S_ISREG(opened.st_mode):
            raise PluginError(f"{label} changed while it was being opened: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
        after = os.fstat(fd)
    finally:
        os.close(fd)
    final = _regular_lstat(path, label, single_link=single_link)
    # Windows reports creation/change time with slightly different precision through
    # ``stat`` and ``fstat``. Size + mtime plus the file identity catch replacement
    # and ordinary writes without producing false positives on an unchanged file.
    stable_fields = (before.st_size, before.st_mtime_ns)
    if (
        _identity(after) != _identity(before)
        or _identity(final) != _identity(before)
        or (after.st_size, after.st_mtime_ns) != stable_fields
        or (final.st_size, final.st_mtime_ns) != stable_fields
    ):
        raise PluginError(f"{label} changed while it was being read: {path}")
    return data, final


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _src_bytes(rel: str) -> bytes:
    safe = _safe_relative(rel, "packaged plugin source")
    base = resources.files("agentrouter") / "integrations"
    source = base.joinpath(*safe.parts)
    if not source.is_file():
        raise PluginError(f"packaged plugin source is missing: {rel}")
    return source.read_bytes()


def _backup_path(root: Path, dest: Path) -> Path:
    relative = dest.relative_to(root)
    backup_rel = relative.with_name(relative.name + _BAK_SUFFIX)
    return _safe_dest(root, backup_rel.as_posix(), "plugin backup")


def _state_path(root: Path, p: Plugin) -> Path:
    return _safe_dest(root, f"{_STATE_DIR}/{p.name}.json", "plugin ownership state")


def _transaction_path(root: Path, p: Plugin) -> Path:
    return _safe_dest(root, f"{_STATE_DIR}/{p.name}.txn.json", "plugin transaction journal")


def _empty_state(p: Plugin) -> dict:
    return {
        "schema": _STATE_SCHEMA,
        "plugin": p.name,
        "state_dir_identity": None,
        "files": {},
        "directories": {},
    }


def _same_payload(path: Path, want: bytes) -> bool:
    if not _path_exists(path):
        return False
    try:
        current, _ = _read_verified(path, "plugin destination")
    except PluginError:
        return False
    return current == want


def _lock_for(root: Path, p: Plugin) -> threading.RLock:
    key = f"{root.resolve(strict=False)}::{p.name}"
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _load_state(root: Path, p: Plugin) -> tuple[dict, str | None]:
    path = _state_path(root, p)
    if not _path_exists(path):
        return _empty_state(p), None
    raw, _ = _read_verified(path, "plugin ownership state")
    try:
        state = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PluginError(
            f"plugin ownership state is invalid; refusing to continue: {path}"
        ) from exc
    if (
        not isinstance(state, dict)
        or state.get("schema") != _STATE_SCHEMA
        or state.get("plugin") != p.name
        or not isinstance(state.get("files"), dict)
        or not isinstance(state.get("directories"), dict)
    ):
        raise PluginError(f"plugin ownership state has an unsupported schema: {path}")
    for relative, entry in state["files"].items():
        _safe_dest(root, relative)
        if not isinstance(entry, dict):
            raise PluginError(
                f"plugin ownership state contains an invalid destination: {relative!r}"
            )
        if entry.get("disposition") not in {"created", "replaced", "preexisting"}:
            raise PluginError(
                f"plugin ownership state contains an invalid disposition: {relative!r}"
            )
        if not isinstance(entry.get("installed_sha256"), str):
            raise PluginError(f"plugin ownership state lacks an installed digest: {relative!r}")
        identity = entry.get("installed_identity")
        if not (
            isinstance(identity, list)
            and len(identity) == 2
            and all(isinstance(x, int) for x in identity)
        ):
            raise PluginError(f"plugin ownership state lacks a valid file identity: {relative!r}")
        backup_rel = entry.get("backup")
        if backup_rel is not None:
            _safe_dest(root, backup_rel, "plugin backup in ownership state")
            if not isinstance(entry.get("backup_sha256"), str):
                raise PluginError(f"plugin ownership state lacks a backup digest: {relative!r}")
            backup_identity = entry.get("backup_identity")
            if not (
                isinstance(backup_identity, list)
                and len(backup_identity) == 2
                and all(isinstance(x, int) for x in backup_identity)
                and isinstance(entry.get("backup_mode"), int)
            ):
                raise PluginError(
                    f"plugin ownership state lacks backup identity metadata: {relative!r}"
                )
    for relative, entry in state["directories"].items():
        _safe_dest(root, relative, "managed plugin directory")
        identity = entry.get("identity") if isinstance(entry, dict) else None
        if not (
            isinstance(identity, list)
            and len(identity) == 2
            and all(isinstance(x, int) for x in identity)
        ):
            raise PluginError(
                f"plugin ownership state has invalid directory identity: {relative!r}"
            )
    state_dir_identity = state.get("state_dir_identity")
    if state_dir_identity is not None and not (
        isinstance(state_dir_identity, list)
        and len(state_dir_identity) == 2
        and all(isinstance(x, int) for x in state_dir_identity)
    ):
        raise PluginError("plugin ownership state has an invalid private-directory identity")
    return state, _sha256(raw)


def _serialized_state(state: dict) -> bytes:
    return (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _temp_file(parent: Path, data: bytes, *, mode: int = 0o600) -> Path:
    """Stage bytes next to their destination, or fail with an actionable error.

    Every other failure in this module raises `PluginError` with a remedy. A
    write failure here used to escape as a bare `OSError`, so a full disk gave
    the user exit 1, no output and a traceback — the one situation where a plain
    sentence ("no space left; free some and retry") is worth most.
    """
    try:
        parent.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix=".agentrouter-tmp-", dir=parent)
    except OSError as exc:
        raise PluginError(
            f"could not prepare a staging file in {parent}: {exc}. "
            "Check free space and that the directory is writable."
        ) from exc
    path = Path(raw_path)
    try:
        # POSIX-only: restrict the temp file to owner before writing. Windows lacks
        # os.fchmod and NTFS ignores POSIX mode bits; mkstemp already creates the
        # file with owner-only access there, so skipping the call is safe.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    except OSError as exc:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise PluginError(
            f"could not write the staging file {path}: {exc}. "
            "Check free space and that the directory is writable."
        ) from exc
    except BaseException:
        # Anything else (KeyboardInterrupt, SystemExit) still propagates, but the
        # partially written staging file is never left behind.
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    os.close(fd)
    return path


def _atomic_replace_bytes(
    root: Path, dest: Path, data: bytes, *, mode: int = 0o600
) -> os.stat_result:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_link_components(root, dest)
    temp = _temp_file(dest.parent, data, mode=mode)
    try:
        _assert_no_link_components(root, dest)
        os.replace(temp, dest)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    _assert_no_link_components(root, dest)
    return _regular_lstat(dest, "new AgentRouter-managed file")


def _create_no_clobber(root: Path, dest: Path, data: bytes, *, mode: int = 0o644) -> os.stat_result:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_link_components(root, dest)
    temp = _temp_file(dest.parent, data, mode=mode)
    try:
        os.link(temp, dest, follow_symlinks=False)
    except FileExistsError:
        raise PluginError(
            f"destination appeared during install; refusing to overwrite it: {dest}"
        ) from None
    except OSError as exc:
        raise PluginError(f"could not create destination atomically {dest}: {exc}") from exc
    finally:
        temp.unlink(missing_ok=True)
    _assert_no_link_components(root, dest)
    return _regular_lstat(dest, "new AgentRouter-managed file")


def _restore_staged_directory(staged: Path, directory: Path) -> None:
    if _path_exists(directory):
        raise PluginError(
            f"directory changed concurrently; preserved the displaced directory at {staged}"
        )
    try:
        os.rename(staged, directory)
    except OSError as exc:
        raise PluginError(
            f"could not restore displaced directory {staged} to {directory}: {exc}"
        ) from exc


def _remove_directory_by_handle(staged: Path, identity: list[int]) -> None:
    """Remove the exact staged directory object, never a pathname replacement."""
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            parent_fd = os.open(staged.parent, flags)
        except OSError as exc:
            raise PluginError(f"could not safely open staged directory parent: {exc}") from exc
        try:
            try:
                info = os.stat(staged.name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError as exc:
                raise PluginError(f"could not verify staged directory identity: {exc}") from exc
            if not stat.S_ISDIR(info.st_mode) or _identity_json(info) != identity:
                raise PluginError("staged directory changed before removal; it was preserved")
            try:
                os.rmdir(staged.name, dir_fd=parent_fd)
            except OSError as exc:
                raise PluginError(f"could not remove the verified staged directory: {exc}") from exc
        finally:
            os.close(parent_fd)
        return

    # Windows has no dir_fd form of rmdir. Mark the verified directory object for
    # deletion through an open handle so a later pathname swap cannot redirect it.
    import ctypes
    import msvcrt
    from ctypes import wintypes

    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    open_directory_no_follow = 0x02000000 | 0x00200000
    file_disposition_info = 4

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(staged),
        delete_access | file_read_attributes,
        share_all,
        None,
        open_existing,
        open_directory_no_follow,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.get_last_error()
        raise PluginError(f"could not safely open staged directory (Windows error {error})")

    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError as exc:
        kernel32.CloseHandle(handle)
        raise PluginError(f"could not bind the staged directory handle: {exc}") from exc

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]

    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or _identity_json(info) != identity:
            raise PluginError("staged directory changed before removal; it was preserved")
        disposition = FileDispositionInfo(True)
        set_information = kernel32.SetFileInformationByHandle
        set_information.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        set_information.restype = wintypes.BOOL
        if not set_information(
            msvcrt.get_osfhandle(fd),
            file_disposition_info,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            error = ctypes.get_last_error()
            raise PluginError(
                f"could not remove the verified staged directory (Windows error {error})"
            )
    finally:
        os.close(fd)


def _remove_owned_empty_directory(root: Path, directory: Path, identity: list[int]) -> str:
    if not _path_exists(directory):
        return "absent"
    info = _directory_lstat(directory, "managed plugin directory")
    if _identity_json(info) != identity:
        return "preserved (directory identity changed)"
    if next(directory.iterdir(), None) is not None:
        return "preserved (not empty)"
    staged = directory.with_name(f".{directory.name}.agentrouter-remove-{uuid.uuid4().hex}")
    try:
        os.rename(directory, staged)
        staged_info = _directory_lstat(staged, "staged managed plugin directory")
        if _identity_json(staged_info) != identity or next(staged.iterdir(), None) is not None:
            _restore_staged_directory(staged, directory)
            return "preserved (directory changed concurrently)"
        _remove_directory_by_handle(staged, identity)
    except (PluginError, OSError) as exc:
        if _path_exists(staged) and not _path_exists(directory):
            try:
                staged_info = _directory_lstat(staged, "staged managed plugin directory")
            except PluginError:
                pass
            else:
                if _identity_json(staged_info) == identity:
                    _restore_staged_directory(staged, directory)
        if isinstance(exc, PluginError):
            raise
        raise PluginError(f"could not remove empty managed directory {directory}: {exc}") from exc
    return "removed (empty directory)"


def _ensure_cleanup_directories(root: Path, p: Plugin, state: dict) -> None:
    for relative in p.cleanup_dirs:
        directory = _safe_dest(root, relative, "plugin cleanup directory")
        if directory == root:
            raise PluginError("plugin cleanup directory may not be the destination root")
        entry = state["directories"].get(relative)
        if _path_exists(directory):
            info = _directory_lstat(directory, "plugin cleanup directory")
            if entry is not None and entry.get("identity") != _identity_json(info):
                raise PluginError(f"managed plugin directory identity changed: {directory}")
            continue
        directory.mkdir(parents=True, exist_ok=False)
        info = _directory_lstat(directory, "new managed plugin directory")
        state["directories"][relative] = {"identity": _identity_json(info)}


def _save_state(root: Path, p: Plugin, state: dict) -> None:
    path = _state_path(root, p)
    state_dir = path.parent
    if not state["files"] and not state["directories"]:
        if _path_exists(path):
            raw, _ = _read_verified(path, "plugin ownership state")
            staged = _stage_exact(root, path, _sha256(raw), None, "plugin ownership state")
            if staged is not None:
                try:
                    staged.unlink()
                except OSError as exc:
                    _restore_staged(staged, path)
                    raise PluginError(f"could not remove plugin ownership state: {exc}") from exc
        expected = state.get("state_dir_identity")
        if expected is not None and _path_exists(state_dir):
            _remove_owned_empty_directory(root, state_dir, expected)
        return
    state_dir.mkdir(parents=True, exist_ok=True)
    info = _directory_lstat(state_dir, "plugin private state directory")
    if state.get("state_dir_identity") is None:
        state["state_dir_identity"] = _identity_json(info)
    elif state["state_dir_identity"] != _identity_json(info):
        raise PluginError("plugin private state directory identity changed; refusing to write")
    _atomic_replace_bytes(root, path, _serialized_state(state), mode=0o600)


def _entry_matches(path: Path, entry: dict, *, backup: bool = False) -> bool:
    if not _path_exists(path):
        return False
    label = "plugin backup" if backup else "managed plugin file"
    try:
        raw, info = _read_verified(path, label)
    except PluginError:
        return False
    if backup:
        return (
            _sha256(raw) == entry.get("backup_sha256")
            and _identity_json(info) == entry.get("backup_identity")
            and stat.S_IMODE(info.st_mode) == entry.get("backup_mode")
        )
    return (
        _sha256(raw) == entry["installed_sha256"]
        and _identity_json(info) == entry["installed_identity"]
    )


def _restore_staged(staged: Path, dest: Path) -> None:
    try:
        os.link(staged, dest, follow_symlinks=False)
    except FileExistsError:
        raise PluginError(
            f"destination changed concurrently; preserved the displaced file at {staged}"
        ) from None
    except OSError as exc:
        raise PluginError(f"could not restore displaced file {staged} to {dest}: {exc}") from exc
    try:
        staged.unlink()
    except OSError as exc:
        try:
            dest_info = dest.lstat()
            staged_info = staged.lstat()
            if _identity(dest_info) == _identity(staged_info):
                dest.unlink()
        except OSError:
            pass
        raise PluginError(
            f"could not finalize displaced-file restoration; preserved it at {staged}: {exc}"
        ) from exc


def _stage_exact(
    root: Path,
    path: Path,
    digest: str,
    identity: list[int] | None,
    label: str,
) -> Path | None:
    """Move a candidate aside, then prove the moved object was the expected one."""
    before_raw, before = _read_verified(path, label)
    if _sha256(before_raw) != digest or (
        identity is not None and _identity_json(before) != identity
    ):
        return None
    staged = path.with_name(f".{path.name}.agentrouter-remove-{uuid.uuid4().hex}")
    _assert_no_link_components(root, path)
    os.rename(path, staged)
    try:
        staged_raw, staged_info = _read_verified(staged, f"staged {label}")
        if _identity(staged_info) != _identity(before) or _sha256(staged_raw) != digest:
            _restore_staged(staged, path)
            return None
    except BaseException:
        if _path_exists(staged) and not _path_exists(path):
            _restore_staged(staged, path)
        raise
    return staged


def _write_transaction(root: Path, p: Plugin, transaction: dict) -> None:
    path = _transaction_path(root, p)
    payload = (json.dumps(transaction, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_replace_bytes(root, path, payload, mode=0o600)


def _load_transaction(root: Path, p: Plugin) -> tuple[dict, str] | None:
    path = _transaction_path(root, p)
    if not _path_exists(path):
        return None
    raw, _ = _read_verified(path, "plugin transaction journal")
    try:
        transaction = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PluginError(f"plugin transaction journal is invalid: {path}") from exc
    if (
        not isinstance(transaction, dict)
        or transaction.get("schema") != 1
        or transaction.get("plugin") != p.name
        or transaction.get("phase") not in {"prepared", "backed_up", "replaced"}
    ):
        raise PluginError(f"plugin transaction journal has an unsupported schema: {path}")
    _safe_dest(root, transaction.get("dest", ""), "journal destination")
    _safe_dest(root, transaction.get("backup", ""), "journal backup")
    return transaction, _sha256(raw)


def _delete_transaction(root: Path, p: Plugin) -> None:
    loaded = _load_transaction(root, p)
    if loaded is None:
        return
    _, digest = loaded
    path = _transaction_path(root, p)
    state_dir = path.parent
    state_dir_info = _directory_lstat(state_dir, "plugin private state directory")
    staged = _stage_exact(root, path, digest, None, "plugin transaction journal")
    if staged is None:
        raise PluginError("plugin transaction journal changed concurrently; it was preserved")
    try:
        staged.unlink()
    except OSError as exc:
        _restore_staged(staged, path)
        raise PluginError(f"could not remove plugin transaction journal: {exc}") from exc
    if not _path_exists(_state_path(root, p)) and _path_exists(state_dir):
        _remove_owned_empty_directory(root, state_dir, _identity_json(state_dir_info))


def _recover_transaction(root: Path, p: Plugin, state: dict) -> None:
    """Finish or roll back an interrupted forced install without guessing ownership."""
    loaded = _load_transaction(root, p)
    if loaded is None:
        return
    transaction, _ = loaded
    dest = _safe_dest(root, transaction["dest"], "journal destination")
    backup = _safe_dest(root, transaction["backup"], "journal backup")
    existing_entry = state["files"].get(transaction["dest"])
    if existing_entry is not None and _entry_matches(dest, existing_entry):
        _delete_transaction(root, p)
        return

    if transaction["phase"] == "prepared":
        if _path_exists(dest):
            try:
                dest_raw, dest_info = _read_verified(
                    dest, "prepared journal destination", single_link=False
                )
            except PluginError:
                dest_raw, dest_info = b"", None
            if (
                dest_info is not None
                and _sha256(dest_raw) == transaction.get("original_sha256")
                and _identity_json(dest_info) == transaction.get("original_identity")
            ):
                # No transaction-owned backup was committed. Any backup path that
                # appeared belongs to another actor and must remain untouched.
                _delete_transaction(root, p)
                return
        raise PluginError(
            "an interrupted prepared install has an unexpected destination; all paths were "
            "preserved for manual recovery"
        )

    backup_ok = False
    backup_info: os.stat_result | None = None
    if _path_exists(backup):
        try:
            backup_raw, backup_info = _read_verified(
                backup, "journaled plugin backup", single_link=False
            )
        except PluginError:
            backup_raw = b""
        backup_ok = (
            (
                _sha256(backup_raw) == transaction.get("original_sha256")
                and _identity_json(backup_info) == transaction.get("original_identity")
                and stat.S_IMODE(backup_info.st_mode) == transaction.get("original_mode")
            )
            if backup_info is not None
            else False
        )

    dest_raw: bytes | None = None
    dest_info: os.stat_result | None = None
    if _path_exists(dest):
        try:
            dest_raw, dest_info = _read_verified(
                dest, "journaled plugin destination", single_link=not backup_ok
            )
        except PluginError:
            pass

    if (
        backup_ok
        and dest_info is not None
        and _identity_json(dest_info) == transaction.get("original_identity")
        and _sha256(dest_raw or b"") == transaction.get("original_sha256")
    ):
        try:
            backup.unlink()
        except OSError as exc:
            raise PluginError(f"could not roll back incomplete backup link: {exc}") from exc
        _delete_transaction(root, p)
        return

    if (
        backup_ok
        and dest_info is not None
        and _sha256(dest_raw or b"") == transaction.get("installed_sha256")
        and _identity_json(dest_info) != transaction.get("original_identity")
    ):
        state["files"][transaction["dest"]] = {
            "disposition": "replaced",
            "installed_sha256": transaction["installed_sha256"],
            "installed_identity": _identity_json(dest_info),
            "backup": transaction["backup"],
            "backup_sha256": transaction["original_sha256"],
            "backup_identity": transaction["original_identity"],
            "backup_mode": transaction["original_mode"],
        }
        _save_state(root, p, state)
        _delete_transaction(root, p)
        return

    if not _path_exists(backup) and dest_info is not None:
        if _sha256(dest_raw or b"") == transaction.get("original_sha256") and _identity_json(
            dest_info
        ) == transaction.get("original_identity"):
            _delete_transaction(root, p)
            return
    raise PluginError(
        "an interrupted plugin install is ambiguous; destination, backup, and journal were "
        "preserved for manual recovery"
    )


def _create_backup(root: Path, dest: Path, backup: Path) -> tuple[str, os.stat_result]:
    """Create an exclusive hard-link backup, preserving metadata and ACLs exactly."""
    before_raw, before = _read_verified(dest, "plugin destination")
    if _path_exists(backup):
        raise PluginError(f"backup already exists at {backup}; refusing to overwrite it.")
    try:
        os.link(dest, backup, follow_symlinks=False)
    except FileExistsError:
        raise PluginError(
            f"backup appeared during install; refusing to overwrite it: {backup}"
        ) from None
    except OSError as exc:
        message = (
            f"could not create a metadata-preserving backup at {backup}; "
            f"destination was not changed: {exc}"
        )
        raise PluginError(message) from exc
    try:
        dest_now = _regular_lstat(dest, "plugin destination", single_link=False)
        backup_now = _regular_lstat(backup, "plugin backup", single_link=False)
        if _identity(dest_now) != _identity(before) or _identity(backup_now) != _identity(before):
            raise PluginError("destination changed while its backup was being created")
        current_raw, _ = _read_verified(dest, "plugin destination", single_link=False)
        if current_raw != before_raw:
            raise PluginError("destination changed while its backup was being created")
        return _sha256(current_raw), backup_now
    except BaseException:
        if _path_exists(backup):
            backup_info = backup.lstat()
            if _identity(backup_info) == _identity(before):
                backup.unlink()
        raise


def _install_entry(
    root: Path,
    p: Plugin,
    f: PluginFile,
    state: dict,
    force: bool,
    adopt_identical: bool,
) -> dict:
    dest = _safe_dest(root, f.dest)
    backup = _backup_path(root, dest)
    want = _src_bytes(f.src)
    want_digest = _sha256(want)
    prior = state["files"].get(f.dest)

    if prior is not None and prior["disposition"] in {"created", "replaced"}:
        if not _entry_matches(dest, prior):
            raise PluginError(
                f"{dest} changed after AgentRouter installed it; "
                "refusing to overwrite the user edit."
            )
        if prior["installed_sha256"] == want_digest:
            return {"kind": "file", "dest": str(dest), "result": "skipped (identical, managed)"}
        staged = _stage_exact(
            root,
            dest,
            prior["installed_sha256"],
            prior["installed_identity"],
            "managed plugin file",
        )
        if staged is None:
            raise PluginError(f"{dest} changed during upgrade; refusing to overwrite it.")
        old_entry = dict(prior)
        new_entry: dict | None = None
        try:
            installed = _create_no_clobber(root, dest, want)
            new_entry = {
                **old_entry,
                "installed_sha256": want_digest,
                "installed_identity": _identity_json(installed),
            }
            state["files"][f.dest] = new_entry
            _save_state(root, p, state)
        except BaseException as exc:
            state["files"][f.dest] = old_entry
            if new_entry is not None and _path_exists(dest):
                displaced_new = _stage_exact(
                    root,
                    dest,
                    new_entry["installed_sha256"],
                    new_entry["installed_identity"],
                    "new managed plugin file",
                )
                if displaced_new is None:
                    raise PluginError(
                        f"upgrade rollback preserved a concurrent edit at {dest}; "
                        f"the prior managed payload is retained at {staged}"
                    ) from exc
                try:
                    displaced_new.unlink()
                except OSError as unlink_exc:
                    raise PluginError(
                        f"upgrade rollback retained the new managed payload at {displaced_new}: "
                        f"{unlink_exc}"
                    ) from exc
            if not _path_exists(dest):
                _restore_staged(staged, dest)
            raise
        try:
            staged.unlink()
        except OSError as exc:
            return {
                "kind": "file",
                "dest": str(dest),
                "result": f"updated (prior managed staging retained at {staged}: {exc})",
            }
        return {"kind": "file", "dest": str(dest), "result": "updated (managed payload)"}

    if _path_exists(dest):
        current, current_info = _read_verified(dest, "plugin destination")
        if current == want:
            state["files"][f.dest] = {
                "disposition": "created" if adopt_identical else "preexisting",
                "installed_sha256": want_digest,
                "installed_identity": _identity_json(current_info),
                "backup": None,
            }
            _save_state(root, p, state)
            result = (
                "adopted identical legacy installation (managed)"
                if adopt_identical
                else "skipped (identical pre-existing file; will be preserved)"
            )
            return {"kind": "file", "dest": str(dest), "result": result}
        if not force:
            raise PluginError(
                f"{dest} exists and differs; re-run with --force to back it up and replace."
            )
        transaction = {
            "schema": 1,
            "plugin": p.name,
            "phase": "prepared",
            "dest": f.dest,
            "backup": backup.relative_to(root).as_posix(),
            "original_sha256": _sha256(current),
            "original_identity": _identity_json(current_info),
            "original_mode": stat.S_IMODE(current_info.st_mode),
            "installed_sha256": want_digest,
        }
        if _path_exists(backup):
            raise PluginError(f"backup already exists at {backup}; refusing to overwrite it.")
        _write_transaction(root, p, transaction)
        try:
            backup_digest, backup_info = _create_backup(root, dest, backup)
        except BaseException as exc:
            try:
                _delete_transaction(root, p)
            except PluginError as journal_exc:
                raise PluginError(
                    f"backup creation failed and its prepared journal was retained: {journal_exc}"
                ) from exc
            raise
        transaction["phase"] = "backed_up"
        _write_transaction(root, p, transaction)
        try:
            installed = _atomic_replace_bytes(root, dest, want)
        except BaseException as exc:
            if _path_exists(dest):
                try:
                    failed_raw, failed_info = _read_verified(
                        dest, "plugin destination after replacement failure", single_link=False
                    )
                except PluginError:
                    failed_raw, failed_info = b"", None
                if (
                    failed_info is not None
                    and _identity_json(failed_info) == transaction["original_identity"]
                    and _sha256(failed_raw) == transaction["original_sha256"]
                ):
                    try:
                        backup.unlink()
                        _delete_transaction(root, p)
                    except OSError as cleanup_exc:
                        raise PluginError(
                            f"replacement failed and rollback cleanup was incomplete: {cleanup_exc}"
                        ) from exc
            raise PluginError(
                f"replacement did not complete cleanly; backup and journal were preserved: {exc}"
            ) from exc
        transaction["phase"] = "replaced"
        transaction["installed_identity"] = _identity_json(installed)
        _write_transaction(root, p, transaction)
        new_entry = {
            "disposition": "replaced",
            "installed_sha256": want_digest,
            "installed_identity": _identity_json(installed),
            "backup": backup.relative_to(root).as_posix(),
            "backup_sha256": backup_digest,
            "backup_identity": _identity_json(backup_info),
            "backup_mode": stat.S_IMODE(backup_info.st_mode),
        }
        state["files"][f.dest] = new_entry
        try:
            _save_state(root, p, state)
        except BaseException as exc:
            state["files"].pop(f.dest, None)
            displaced_new = _stage_exact(
                root,
                dest,
                want_digest,
                _identity_json(installed),
                "new managed plugin file",
            )
            if displaced_new is None:
                raise PluginError(
                    f"state rollback preserved a concurrent edit at {dest}; "
                    "the original backup and transaction journal were retained"
                ) from exc
            try:
                _restore_backup(root, backup, dest)
                displaced_new.unlink()
                _delete_transaction(root, p)
            except BaseException as rollback_exc:
                if not _path_exists(dest) and _path_exists(displaced_new):
                    _restore_staged(displaced_new, dest)
                raise PluginError(
                    f"forced-install rollback was incomplete: {rollback_exc}"
                ) from exc
            raise
        _delete_transaction(root, p)
        return {
            "kind": "file",
            "dest": str(dest),
            "result": f"replaced (backup: {backup.name})",
        }

    installed = _create_no_clobber(root, dest, want)
    state["files"][f.dest] = {
        "disposition": "created",
        "installed_sha256": want_digest,
        "installed_identity": _identity_json(installed),
        "backup": None,
    }
    try:
        _save_state(root, p, state)
    except BaseException as exc:
        state["files"].pop(f.dest, None)
        staged = _stage_exact(
            root, dest, want_digest, _identity_json(installed), "managed plugin file"
        )
        if staged is not None:
            try:
                staged.unlink()
            except OSError as unlink_exc:
                raise PluginError(
                    f"install rollback retained the managed staging file at {staged}: {unlink_exc}"
                ) from exc
        raise
    return {"kind": "file", "dest": str(dest), "result": "created"}


def plan(p: Plugin, *, adopt_identical: bool = False) -> list[dict]:
    """Describe install changes without changing the filesystem."""
    root = dest_root(p)
    state, _ = _load_state(root, p)
    out: list[dict] = []
    for f in p.files:
        dest = _safe_dest(root, f.dest)
        want = _src_bytes(f.src)
        entry = state["files"].get(f.dest)
        if not _path_exists(dest):
            action = "create"
        elif (
            entry
            and entry["disposition"] in {"created", "replaced"}
            and _entry_matches(dest, entry)
            and _sha256(want) == entry["installed_sha256"]
        ):
            action = "skip (identical, managed)"
        elif _same_payload(dest, want):
            action = (
                "adopt identical legacy installation (managed)"
                if adopt_identical
                else "record pre-existing (preserved on uninstall)"
            )
        else:
            try:
                _regular_lstat(dest, "plugin destination")
            except PluginError:
                action = "blocked (not a safe regular file)"
            else:
                action = "overwrite (backup first)"
        out.append({"kind": "file", "dest": str(dest), "action": action})
    return out


def status(p: Plugin) -> str:
    root = dest_root(p)
    present = [_path_exists(_safe_dest(root, f.dest)) for f in p.files]
    if all(present):
        return "installed"
    if any(present):
        return "partial"
    return "not-installed"


def install(p: Plugin, force: bool = False, adopt_identical: bool = False) -> list[dict]:
    """Install bundled files and persist enough ownership data for safe uninstall."""
    root = dest_root(p)
    results: list[dict] = []
    with _lock_for(root, p):
        state, _ = _load_state(root, p)
        _recover_transaction(root, p, state)
        # Validate all registry paths and packaged resources before any mutation.
        for f in p.files:
            _safe_dest(root, f.dest)
            _backup_path(root, _safe_dest(root, f.dest))
            _src_bytes(f.src)
        historical = sorted(set(state["files"]) - {f.dest for f in p.files})
        if historical:
            raise PluginError(
                "plugin registry paths changed; run uninstall to safely remove historical managed "
                f"paths first: {', '.join(historical)}"
            )
        before_directories = dict(state["directories"])
        _ensure_cleanup_directories(root, p, state)
        if state["directories"] != before_directories:
            _save_state(root, p, state)
        for f in p.files:
            try:
                results.append(_install_entry(root, p, f, state, force, adopt_identical))
            except (PluginError, OSError) as exc:
                raise PluginError(str(exc), results=results) from exc
    return results


def _restore_backup(root: Path, backup: Path, dest: Path) -> None:
    """Restore by link-then-unlink so a concurrently-created destination is never clobbered."""
    _assert_no_link_components(root, backup)
    _assert_no_link_components(root, dest)
    try:
        os.link(backup, dest, follow_symlinks=False)
    except FileExistsError:
        raise PluginError(f"destination appeared during restore; backup retained: {dest}") from None
    except OSError as exc:
        raise PluginError(f"could not restore backup {backup} to {dest}: {exc}") from exc
    try:
        backup.unlink()
    except OSError as exc:
        try:
            dest_info = dest.lstat()
            backup_info = backup.lstat()
            if _identity(dest_info) == _identity(backup_info):
                dest.unlink()
        except OSError:
            pass
        raise PluginError(f"could not finalize backup restore; backup retained: {exc}") from exc


def _uninstall_entry(root: Path, f: PluginFile, state: dict) -> dict:
    dest = _safe_dest(root, f.dest)
    entry = state["files"].get(f.dest)
    if entry is None:
        result = "preserved (unmanaged)" if _path_exists(dest) else "absent"
        return {"kind": "file", "dest": str(dest), "result": result}
    if entry["disposition"] == "preexisting":
        del state["files"][f.dest]
        return {"kind": "file", "dest": str(dest), "result": "preserved (pre-existing)"}

    backup_rel = entry.get("backup")
    backup = _safe_dest(root, backup_rel, "plugin backup") if backup_rel else None
    if backup is not None and not _path_exists(backup) and _path_exists(dest):
        try:
            restored_raw, restored_info = _read_verified(dest, "restored plugin backup")
        except PluginError:
            pass
        else:
            if (
                _sha256(restored_raw) == entry.get("backup_sha256")
                and _identity_json(restored_info) == entry.get("backup_identity")
                and stat.S_IMODE(restored_info.st_mode) == entry.get("backup_mode")
            ):
                del state["files"][f.dest]
                return {
                    "kind": "file",
                    "dest": str(dest),
                    "result": "recovered completed backup restoration",
                }
    if backup is not None and (
        not _path_exists(backup) or not _entry_matches(backup, entry, backup=True)
    ):
        return {
            "kind": "file",
            "dest": str(dest),
            "result": "preserved (backup missing or changed; ownership is ambiguous)",
        }

    if not _path_exists(dest):
        if backup is None:
            del state["files"][f.dest]
            return {"kind": "file", "dest": str(dest), "result": "absent"}
        _restore_backup(root, backup, dest)
        del state["files"][f.dest]
        return {
            "kind": "file",
            "dest": str(dest),
            "result": "restored backup (managed file was absent)",
        }

    if not _entry_matches(dest, entry):
        suffix = "; backup retained" if backup is not None else ""
        return {
            "kind": "file",
            "dest": str(dest),
            "result": f"preserved (not the unchanged managed file){suffix}",
        }

    staged = _stage_exact(
        root, dest, entry["installed_sha256"], entry["installed_identity"], "managed plugin file"
    )
    if staged is None:
        return {"kind": "file", "dest": str(dest), "result": "preserved (changed concurrently)"}
    if backup is not None:
        try:
            _restore_backup(root, backup, dest)
        except BaseException:
            if not _path_exists(dest):
                _restore_staged(staged, dest)
            raise
        try:
            staged.unlink()
            result = "removed (restored backup)"
        except OSError as exc:
            result = f"removed (restored backup; managed staging retained at {staged}: {exc})"
    else:
        try:
            staged.unlink()
        except OSError as exc:
            _restore_staged(staged, dest)
            raise PluginError(f"could not remove managed plugin file: {exc}") from exc
        result = "removed"
    del state["files"][f.dest]
    return {"kind": "file", "dest": str(dest), "result": result}


def uninstall(p: Plugin) -> list[dict]:
    """Remove only proven managed files, restore backups, and prune declared empty dirs."""
    root = dest_root(p)
    results: list[dict] = []
    with _lock_for(root, p):
        state, _ = _load_state(root, p)
        _recover_transaction(root, p, state)
        for f in p.files:
            _safe_dest(root, f.dest)
        for relative in p.cleanup_dirs:
            directory = _safe_dest(root, relative, "plugin cleanup directory")
            if directory == root:
                raise PluginError("plugin cleanup directory may not be the destination root")

        registry_by_dest = {f.dest: f for f in p.files}
        destinations = list(state["files"])
        destinations.extend(dest for dest in registry_by_dest if dest not in state["files"])
        for relative in destinations:
            f = registry_by_dest.get(relative, PluginFile("", relative))
            try:
                result = _uninstall_entry(root, f, state)
                results.append(result)
                _save_state(root, p, state)
            except (PluginError, OSError) as exc:
                raise PluginError(str(exc), results=results) from exc

        cleanup_relatives = list(state["directories"])
        cleanup_relatives.extend(
            relative for relative in p.cleanup_dirs if relative not in state["directories"]
        )
        for relative in cleanup_relatives:
            directory = _safe_dest(root, relative, "plugin cleanup directory")
            entry = state["directories"].get(relative)
            try:
                if entry is None:
                    result = (
                        "preserved (unmanaged directory)" if _path_exists(directory) else "absent"
                    )
                else:
                    result = _remove_owned_empty_directory(root, directory, entry["identity"])
                    if result in {"absent", "removed (empty directory)"}:
                        del state["directories"][relative]
                    _save_state(root, p, state)
            except (PluginError, OSError) as exc:
                raise PluginError(str(exc), results=results) from exc
            results.append({"kind": "directory", "dest": str(directory), "result": result})
    return results
