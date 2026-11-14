# TASK-018A adversarial security re-review (closing the gap)

The fresh security re-review commissioned during TASK-018A **never returned** —
the session running it hit a usage limit. That gap was recorded rather than
papered over, and this closes it.

Run: 2026-08-19, against the merged TASK-018A surfaces at RC `c11ddec` plus the
TASK-018B changes on top. Every case was **executed**, not reasoned about.

## Result

**No new critical or high findings.** Every previously-fixed defect was re-attacked
with its original reproduction and none of them came back. One known limitation
was re-confirmed and is already scheduled for TASK-018C.

## What was attacked, and what happened

| # | Attack | Result |
|---|--------|--------|
| A1 | Baseline tampering — blank a referenced component to `{}` | Reports `compatible=True` locally. **Known and documented** in AD-5: `validate_refs` does not catch this; the control is the base-branch check in CI, which compares against a contract the PR author does not control. Not a regression. |
| A2 | `$ref` bombs — self-referential, remote, dangling | All three **rejected** with a precise reason. |
| A3 | Schema-complexity DoS — 30-level fan-out × 50 paths | **Refused in 0.00 s.** The shared budget holds; no `RecursionError` escaped. |
| A4 | Unauthenticated `/ready` log amplification (the original HIGH) | **202 bytes/request**, no registry path, no credential, no traceback. Was ~8 KB. |
| A5 | Secret redaction | A real Google API key is **masked**. An ordinary file path is **also** masked — the known over-match, see below. |
| A6 | Malicious identifiers — traversal, 9 KB id, CRLF | 404/422, bodies ≤ 104 bytes, no traceback, no path leak, **no injected header**. |
| A7 | Write-target attacks — symlink out, **hardlink**, contract dir symlinked out | All three **refused**; the victim file was intact in every case. |
| A8 | Parity server temp resources | Binds **loopback only**; temp home cleaned on SIGTERM; no leak. |

## Carried forward to TASK-018C (not a regression, not new)

**Redaction over-matches ordinary file paths.** `_SECRET_RE`'s generic
`[A-Za-z0-9+/]{40,}` alternative matches long path-like runs, so a traceback
renders as `04 - Dev [redacted].py`. This is the **safe** failure direction — it
over-redacts rather than under-redacts — but it costs diagnosability in exactly
the situation where a traceback matters most.

It must be fixed **without weakening secret detection**: the correct approach is
to make the generic high-entropy alternative more selective (e.g. require a digit,
or exclude runs that parse as a filesystem path), never to drop it.

## Honest limits of this review

I performed this pass myself rather than delegating it, because the delegated
attempt is what failed. That means it is not independent in the sense a separate
reviewer would be. It is, however, entirely reproducible: every case above is a
script that either raises or does not, and the assertions are in the committed
test suites rather than in this document.
