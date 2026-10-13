# Acceptance

**User problem**: AgentRouter's `doctor` could not say what invoked it, and
had no concept of provider quota/usage distinct from "is a credential
present" — so a strong model recommendation could silently fail against an
exhausted account, and pre-flight reporting couldn't distinguish "we don't
know" from "unsupported" from "actually out of budget."

**Expected outcome**: `doctor` always reports harness identity (evidence-based,
honest UNKNOWN/GENERIC when uncertain); `doctor --verify-live` and
`route --verify-live` add an opt-in, honest, isolated, sanitized,
bounded-timeout usage/quota check that never fabricates a number and re-ranks
away a live-confirmed-exhausted top pick — with zero behavior/output change
for anyone not passing the new flag.

**Per-criterion evidence**: see task.yaml's `acceptance_criteria` list;
verification-engineer's independent report (this session, pre-repair) traced
each to file:line and a reproduced test/command result; release-check.md
restates the post-repair evidence for the same criteria plus the five
repaired findings.
