# Repair loop — TASK-003 (1 iteration)

1. Weak property (verification finding): approval-mapping test used the module's own
   _APPROVAL dict on both sides -> would not catch a corrupted table.
   - fix: assert against an independent literal EXPECTED_APPROVAL in the test.
   - re-verify: pytest tests/test_property.py -q -> 6 passed; full suite 405 passed.

Mutation-testing execution: NOT a repairable code defect — environment incompatibility
(Windows + Python 3.13 vs mutmut 2.x/3.x and mutatest 3.1). Root-caused, not looped;
documented in KNOWN_LIMITATIONS as a Linux-CI/WSL follow-up. No fabricated score.
