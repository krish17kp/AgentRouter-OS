# Operational runbooks

Every procedure below is labelled by how much it has actually been proven:

- **Verified** — exercised by a test in this repository. The test name is given,
  so you can read what "verified" means rather than taking the word for it.
- **Local procedure** — a real command against a local install, exercised by
  hand but not asserted in CI.
- **Hypothetical** — written from first principles for infrastructure this
  project does not have. Treat it as a starting point, not a tested procedure.

Start every investigation the same way:

```bash
agentrouter doctor          # human-readable, with a remedy per problem
agentrouter doctor --json   # same thing for a script
```

Exit code `0` means the installation works; `1` means something is broken.
Warnings do not fail — open local mode with no API key is the documented default.

---

## 1. First run / clean installation — **Verified**

```bash
pip install "agentrouter-os[server]"
agentrouter init
agentrouter doctor
agentrouter route "write a unit test for the parser"
```

`doctor` will warn that `AGENTROUTER_API_KEY` is unset. That is expected: the
local API is open by default.

*Verified by* `tests/test_diagnostics.py::test_a_healthy_install_reports_no_failures_and_exits_zero`
and the clean-wheel install exercised in CI's `build-smoke` job.

---

## 2. "database is locked" under concurrent use — **Verified**

**Symptom:** intermittent `500 internal_error` from `POST /v1/route` while
several clients route at once; the server log shows
`sqlite3.OperationalError: database is locked`.

**Cause:** SQLite allows one writer at a time, and its default busy timeout is
zero — the first contended write fails outright instead of waiting.

**Check:**

```bash
agentrouter doctor --json | python -c "import json,sys; \
print([c for c in json.load(sys.stdin)['checks'] if c['id']=='data.database'])"
```

`journal_mode` must be `wal`. If it says anything else, the database was created
by a version before this was fixed.

**Fix:** upgrade. Since TASK-018B the store opens WAL with a 15-second busy
timeout *and* serialises writers in-process, so they queue instead of racing.
An older database is migrated on the next `store.connect`, which every command
performs.

*Verified by* `tests/test_reliability_load.py::test_concurrent_routing_produces_no_server_errors_and_loses_no_writes`
(200 concurrent routes, zero 5xx, zero lost writes) and
`::test_the_store_waits_for_a_contended_write_instead_of_failing`.

---

## 3. Backing up or moving the decision log — **Verified**

**Do not copy `agentrouter.db` with `cp`.** With a WAL active, committed rows
live in `agentrouter.db-wal` until a checkpoint, so a plain copy silently
produces a database with **zero rows** — no error, no warning.

```bash
agentrouter doctor --bundle ./ar-bundle --include-database
```

That writes `decisions.db` through SQLite's online backup API: consistent,
complete, and one self-contained file. It works while the server is running.

*Verified by* `tests/test_reliability_load.py::test_a_naive_file_copy_of_the_database_is_not_a_backup`
(which pins the hazard) and `::test_snapshot_captures_rows_still_held_in_the_wal`.

---

## 4. Database corruption — **Local procedure**

`agentrouter doctor` reports `data.database` as `fail` with the
`PRAGMA integrity_check` output when the file is damaged.

1. Stop anything using it.
2. Move it aside — do not delete it: `mv ~/.agentrouter/agentrouter.db{,.broken}`
3. `agentrouter init` recreates an empty log.
4. If you have a bundle from procedure 3, its `decisions.db` is a valid
   database; copy it back into place as `agentrouter.db`.

The decision log is telemetry, not source of truth: losing it costs history and
`agentrouter stats`, nothing else.

---

## 5. Corrupted or stale provider catalog — **Verified**

```bash
agentrouter providers doctor          # which catalog, and why
agentrouter providers status          # age and provenance
agentrouter providers rollback <provider>   # revert to the previous copy
agentrouter providers restore <provider>    # undo a rollback
```

`doctor`'s `catalogs.generated` check reports stale catalogs as a warning and
unreadable ones as a failure. A corrupt catalog never crashes the CLI or the
API; it produces a typed error and exit code 3.

*Verified by* `tests/test_failure_injection.py::test_corrupt_registry_is_typed_not_a_crash`,
which injects malformed YAML, non-UTF8 bytes, a wrong root type, a truncated
mid-write file and an empty file.

---

## 6. API returns 429 under load — **Verified**

429 with `Retry-After` is the rate limiter shedding load correctly, not a fault.
It is **opt-in**: unset unless `AGENTROUTER_RATE_LIMIT` is set.

```bash
unset AGENTROUTER_RATE_LIMIT              # disable
export AGENTROUTER_RATE_LIMIT=600         # or raise, per AGENTROUTER_RATE_WINDOW (default 60s)
```

Counters are per-process and in memory, so behind multiple workers each gets its
own budget. `/health` and `/ready` are never rate limited — a throttled probe
would take a healthy service out of rotation.

*Verified by* `tests/test_reliability_load.py::test_rate_limiting_sheds_load_without_dropping_the_envelope`
and `::test_probes_are_never_rate_limited`.

---

## 7. Idempotency: a retry produced two decisions — **Verified**

It should not, and since TASK-018B it does not. Concurrent requests carrying the
same `Idempotency-Key` and body are serialised per key: the first runs, the rest
replay its response with `Idempotency-Replay: true`.

If you see two decisions, check that both requests really carried the same key
**and** the same body — the cache key includes a body hash on purpose, so a
reused key with a different payload deliberately does *not* replay.

*Verified by* `tests/test_reliability_load.py::test_a_replayed_idempotency_key_creates_exactly_one_decision`
(12 concurrent replays produce exactly one decision) and
`::test_the_same_key_with_a_different_body_does_not_replay`.

---

## 8. No execution host is ready — **Verified**

```bash
agentrouter hosts doctor    # per-host state and the cheapest concrete fix
```

States are `missing` (not installed), `installed`, `configured`,
`authenticated` (a credential exists) and `degraded`. `authorized` is never
returned offline, because proving it needs a live call this project does not
make — `authenticated` means a credential exists, never that it was accepted.

A set-but-blank credential reports `degraded`, not available.

*Verified by* the TASK-016 suite and
`tests/test_diagnostics.py::test_a_blank_api_key_is_a_failure_not_a_pass`.

---

## 9. Collecting a bundle for a support request — **Verified**

```bash
agentrouter doctor --bundle ./ar-bundle
```

Contains diagnostics, versions, which settings are set, and the *shape* of the
decision log. It never contains a `.env`, a credential file, or an API key
value, and it is assembled from an allowlist rather than by scanning a
directory.

`--include-database` adds your decision log, which **contains the task text you
routed**. The README inside the bundle says so. Review before sharing.

*Verified by* `tests/test_bundle.py` — ten tests, each attacking one way
something private could get in.

---

## 10. The project volume remounts read-only (NTFS) — **Verified (detection)**

This has actually happened on the development machine. Symptoms: every write
fails with `Read-only file system`, and `doctor` reports `data.home` as `fail`.

```bash
findmnt -T "$PWD" -o TARGET,SOURCE,FSTYPE,OPTIONS   # look for `ro` in OPTIONS
```

Recovery is a **local procedure**, and it is deliberate rather than automatic —
forcing a dirty NTFS volume back to read-write risks corruption:

```bash
sudo umount "/media/<user>/<volume>"
sudo ntfsfix /dev/<partition>        # clears a dirty flag; NOT a chkdsk substitute
sudo mount -o rw /dev/<partition> "/media/<user>/<volume>"
```

If `ntfsfix` says the volume needs `chkdsk`, boot Windows and let it run.

*Detection verified by* `tests/test_diagnostics.py::test_an_unwritable_home_is_reported_with_the_mount_hint`
and `tests/test_failure_injection.py::test_read_only_data_directory_does_not_leak_or_crash`.

---

## 11. Correlating a user report with the logs — **Verified**

Every response carries `X-Request-ID`, echoed if the client sent one. The same
id appears in the structured log record for that request, including on the error
path.

```bash
export AGENTROUTER_LOG=1     # structured records are opt-in
```

*Verified by* `tests/test_observability_correlation.py` — the id reaches the log
on success and on failure, is unique per request, and is cleared afterwards so
it cannot bleed into a later call.

---

## 12. Production incident response — **Hypothetical**

AgentRouter OS is a local-first tool. It has no hosted deployment, no shared
database and no on-call rotation, so there is nothing here that has been
exercised against real infrastructure.

If you deploy it behind a shared service, the parts that would need real work
first: the rate limiter is per-process, the idempotency cache is in memory, and
SQLite's single-writer model is the throughput ceiling. Those are design
statements, not tuning advice, and none of them has been tested at scale.

Anything else you may want here — backup rotation, failover, capacity planning —
would be invention. It is deliberately absent.
