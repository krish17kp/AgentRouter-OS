# TASK-165 — Windows release-candidate CI repair

Repair two hosted Windows-only failures without weakening tests: deterministic
evaluation CLI process discovery must not be bypassed by Windows executable
search order, and diagnostic bundle exclusive creation must never follow a
final-component dangling symlink introduced at the open boundary.
