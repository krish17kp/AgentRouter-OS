# TASK-196 evidence

Date: 2026-11-17

```console
uv run --with '.[dev,server,security]' pytest -q \
  tests/test_rust_banking77_compat.py \
  tests/test_rust_clinc150_compat.py \
  tests/test_rust_longbench_compat.py \
  tests/test_rust_massive_compat.py \
  tests/test_rust_swebench_compat.py \
  tests/test_rust_evaluation_adapter_base_compat.py
# 17 passed in 3.40s
```

The differential suite remains fixture/offline only. Rust real HuggingFace
loading remains an explicit external blocker and no fallback was introduced.
