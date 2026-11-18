# Rust runner environment contract

The evaluation report's `environment` object describes the runtime that
actually produced it. Python and Rust therefore share provenance semantics, not
false interpreter labels.

| Meaning | Python field | Rust field |
|---|---|---|
| AgentRouter package version | `agentrouter_version` | `agentrouter_version` |
| Runtime identity/version | `python` | `runtime="rust"`, `rustc` |
| Platform identity | `platform` | `platform` (`OS-ARCH`) |
| repository commit | `git_sha` | `git_sha` |
| repository working-tree state | `git_dirty` | `git_dirty` |
| classifier implementation identity | `classifier_sha256` (Python source) | `classifier_sha256` (embedded Rust source) |

Git and compiler probes are silent, read-only, and bounded to five seconds.
Missing executables, nonzero exits, invalid/empty UTF-8 output, and timeouts
produce JSON `null`; they never abort an otherwise valid offline evaluation.
Classifier identity is compile-time embedded and always a lowercase SHA-256
hex digest. Large dirty-tree output is drained concurrently so it cannot block
the child process on a full pipe.
