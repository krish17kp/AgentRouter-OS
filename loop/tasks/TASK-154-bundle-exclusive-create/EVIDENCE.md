# TASK-154 evidence

Baseline at `82babba`: Python `bundle._write()` replaced an existing artifact;
the Rust writer already used exclusive creation and refused that operation.

The Python writer now opens the final artifact in binary exclusive-create mode.
Focused bundle and observability selection passes 95 tests with 1 skip; the
bundle-only selection passes 27 tests. Existing JSON/text artifacts, live and
dangling symlinks, and a final-path file or symlink appearing immediately before
open are refused without changing the existing file or referent. Ruff and format
checks pass.

Independent review found no blocking defect and confirmed the race tests are
meaningful and portable. The scope protects the final artifact path. Parent
directory replacement and cleanup after a mid-write I/O failure remain separate
filesystem-hardening work. Full regression passes 2,604/7 in 561.79 seconds
with 92.021% statement, 87.833% branch, and 91.058% combined coverage. The
wheel/sdist build, installed-wheel exclusive-create smoke, Bandit, and 33 hook
tests pass. Hosted validation follows the RC push.
