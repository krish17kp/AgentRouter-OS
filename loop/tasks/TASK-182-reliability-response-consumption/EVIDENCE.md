# TASK-182 evidence

- Rust response handling now drains `ureq` bodies before recording an HTTP
  status.
- Incomplete bodies become `ReadError`/`ReadTimeout` transport errors rather
  than falsely counted HTTP successes.
- The Python/Rust reliability differential adds a truncated-body regression;
  the Python side reports `RemoteProtocolError`, while Rust reports its stable
  `ReadError` category.
- Full workspace validation and focused reliability validation are required
  before this slice can be pushed or considered parity-complete.
