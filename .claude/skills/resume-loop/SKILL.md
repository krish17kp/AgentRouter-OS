---
name: resume-loop
description: Resume the AgentRouter OS production loop in a fresh session. Use at session start, when the user says "resume", "continue the loop", or "where were we". Reconstructs exact state from persisted files, no conversation memory needed.
---

# Resume Loop

1. Read `LOOP_STATE.json` (status, iteration, current task, next_action,
   blocked lists) and the newest entry in `LOOP_LOG.md`.
2. Read the newest `loop/handoffs/*.md` if present — it has the paste-ready
   continuation (files changed, tests run, failures, next command).
3. Read the active `loop/tasks/TASK-*/` dir: `task.yaml` status +
   `implementation-log.md` + `audit.md` to see where the task stopped.
4. Re-establish the baseline (`python -m pytest -q`) before continuing — never
   trust a stale green.
5. Continue from the exact loop step recorded, or select the next
   `local_open` backlog item if the last task reached a terminal state.

Do not restart completed work. Do not fabricate progress.
