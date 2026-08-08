"""Unit tests for AgentRouter OS Claude Code hooks.

Run: python -m pytest .claude/hooks/test_hooks.py -q
Invokes each hook as a subprocess with a JSON event on stdin and asserts the
exit code (0 = allow, 2 = block).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).parent


def run_hook(script: str, event: dict) -> int:
    proc = subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def bash_at(cmd: str, cwd) -> dict:
    """A Bash event carrying the cwd the hook should resolve the branch from."""
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd)}


def repo_on(tmp_path, branch: str):
    """A throwaway git repo with one commit, checked out on `branch`."""
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(tmp_path), *a], check=True, capture_output=True
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "test")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-q", "-m", "init")
    run("checkout", "-q", "-B", branch)
    return tmp_path


TASK_BRANCH = "task/TASK-999-example"
RC_BRANCH = "release/agentrouter-v0.5-rc1"


# ---- pre_tool_guard ----


def test_blocks_git_push():
    assert run_hook("pre_tool_guard.py", bash("git push origin main")) == 2


# ---- pre_tool_guard: branch-aware git write policy ----


def test_allows_git_add_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git add file.py", repo)) == 0


def test_allows_git_commit_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git commit -m 'work'", repo)) == 0


def test_allows_git_push_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git push", repo)) == 0


def test_allows_git_push_set_upstream_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        f"git push -u origin {TASK_BRANCH}",
        f"git push --set-upstream origin {TASK_BRANCH}",
        f"git push origin {TASK_BRANCH}",
        "git push origin HEAD",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 0, cmd


def test_blocks_git_writes_on_main(tmp_path):
    repo = repo_on(tmp_path, "main")
    for cmd in ("git add file.py", "git commit -m x", "git push"):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_git_writes_on_release_candidate(tmp_path):
    repo = repo_on(tmp_path, RC_BRANCH)
    for cmd in ("git add file.py", "git commit -m x", "git push"):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_task_branch_pushing_to_protected_branches(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        "git push origin main",
        f"git push origin {RC_BRANCH}",
        "git push origin HEAD:main",
        f"git push origin HEAD:{RC_BRANCH}",
        f"git push origin {TASK_BRANCH}:main",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_push_refspec_for_a_different_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git push origin task/other", repo)) == 2


def test_blocks_force_push_even_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        "git push --force",
        "git push -f origin " + TASK_BRANCH,
        "git push --force-with-lease",
        "git push -uf origin " + TASK_BRANCH,
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_remote_branch_deletion(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git push origin --delete other", repo)) == 2


def test_blocks_tags_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    assert run_hook("pre_tool_guard.py", bash_at("git tag v1.0.0", repo)) == 2


def test_blocks_history_rewrite_and_destructive_git_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        "git rebase -i HEAD~3",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git filter-branch --tree-filter x",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_destructive_and_owner_only_commands_on_task_branch(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        "rm -rf data/",
        "twine upload dist/*",
        "railway up",
        "echo $OPENAI_API_KEY",
        "python -c 'subprocess.run(x, shell=True)'",
        "claude --dangerously-skip-permissions",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_allows_reads_and_branch_creation_on_protected_branch(tmp_path):
    repo = repo_on(tmp_path, RC_BRANCH)
    for cmd in (
        "git status --short",
        "git log --oneline -5",
        "git fetch origin --prune",
        f"git checkout -b {TASK_BRANCH}",
        "git diff --stat",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 0, cmd


def test_compound_command_is_blocked_if_any_segment_violates(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    cmd = "git add . && git commit -m ok && git push origin main"
    assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2


def test_compound_task_branch_workflow_is_allowed(tmp_path):
    repo = repo_on(tmp_path, TASK_BRANCH)
    cmd = f"git add . && git commit -m ok && git push -u origin {TASK_BRANCH}"
    assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 0


def test_blocks_git_write_when_branch_undeterminable(tmp_path):
    """No git repo at cwd: push must fail closed, not open."""
    assert run_hook("pre_tool_guard.py", bash_at("git push", tmp_path)) == 2


def test_shell_redirections_are_not_mistaken_for_refspecs(tmp_path):
    """`2>&1`, `> file` etc. are redirections, not push targets."""
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        f"git push -u origin {TASK_BRANCH} 2>&1",
        f"git push origin {TASK_BRANCH} > out.log 2>&1",
        "git push 2>/dev/null",
        f"git push -u origin {TASK_BRANCH} 2>&1 | tail -5",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 0, cmd


def test_redirection_stripping_does_not_hide_a_protected_target(tmp_path):
    """Stripping redirections must not let a protected refspec slip through."""
    repo = repo_on(tmp_path, TASK_BRANCH)
    for cmd in (
        "git push origin main 2>&1",
        "git push origin HEAD:main > out.log",
    ):
        assert run_hook("pre_tool_guard.py", bash_at(cmd, repo)) == 2, cmd


def test_blocks_rm_rf():
    assert run_hook("pre_tool_guard.py", bash("rm -rf data/")) == 2


def test_blocks_shell_true():
    assert run_hook("pre_tool_guard.py", bash("python -c 'subprocess.run(x, shell=True)'")) == 2


def test_blocks_secret_print():
    assert run_hook("pre_tool_guard.py", bash("echo $OPENAI_API_KEY")) == 2


def test_blocks_deploy():
    assert run_hook("pre_tool_guard.py", bash("railway up")) == 2


def test_blocks_publish():
    assert run_hook("pre_tool_guard.py", bash("twine upload dist/*")) == 2


def test_allows_safe_command():
    assert run_hook("pre_tool_guard.py", bash("python -m pytest -q")) == 0


def test_allows_git_read():
    assert run_hook("pre_tool_guard.py", bash("git log --oneline -5")) == 0


def test_allows_non_bash():
    assert run_hook("pre_tool_guard.py", {"tool_name": "Read", "tool_input": {}}) == 0


def test_pre_guard_fails_open_on_empty():
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "pre_tool_guard.py")],
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


# ---- stop_gate ----


def test_stop_allows_when_no_state(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


def test_stop_blocks_ready_without_passing(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "PRODUCTION_READY", "last_test_results": {"result": "3 failed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2


def test_stop_allows_ready_with_passing(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "PRODUCTION_READY", "last_test_results": {"result": "371 passed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0


def test_stop_allows_non_ready_status(tmp_path):
    (tmp_path / "LOOP_STATE.json").write_text(
        json.dumps({"status": "BLOCKED_EXTERNAL", "last_test_results": {"result": "371 passed"}}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "stop_gate.py")],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
