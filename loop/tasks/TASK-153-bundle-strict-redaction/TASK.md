# TASK-153 — Strict diagnostic bundle privacy

Recover the lost uncommitted bundle privacy changes from the interrupted temporary checkout.
Redact text before UTF-8 byte truncation, including the suffix in the cap. Redact JSON
structurally, mask sensitive fields and deep containers, and reject malformed/oversized
JSON before writing. Preserve Python/Rust parity and presence-only environment sentinels.

No frozen data or release thresholds change. Full regression and independent review required.
