# Rust annotation workflow

The evaluation executable now includes the offline context-band review flow:

```sh
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset gen-candidates --out candidates.yaml --count 120 --seed 20260731
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset pack --annotator A --seed 101 --candidates candidates.yaml --out pack_A.yaml
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset annotate pack_A.yaml --annotator A --out labels_A.jsonl
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset progress pack_A.yaml --labels labels_A.jsonl
```

Each annotator must work from their own independently ordered pack and labels
file. The `annotate` command asks the person at the terminal for a band,
rationale, and confidence, then saves each completed item immediately. Running
it again resumes from candidate IDs already in that labels file. End input with
EOF to pause and resume later. It does not infer, suggest, or auto-fill labels.

To inspect disagreements and build a reviewed development set:

```sh
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset adjudication-pack --labels labels_A.jsonl --labels labels_B.jsonl --out adjudication.yaml
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset build --labels labels_A.jsonl --labels labels_B.jsonl --adjudications adjudications.json --out-dir artifacts/context-band --version v2.0.0
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset compare artifacts/context-band/context_band_dev_v2.0.0.yaml --out artifacts/context-band/comparison.json
cargo run --locked -p agentrouter-evaluation --bin agentrouter-evaluate -- dataset leakage artifacts/context-band/context_band_holdout_v2.0.0.yaml
```

`build` refuses unresolved conflicts and checks the new development/private
holdout splits against frozen holdout prompts without reading frozen labels.
The CLI compatibility slice is partial: the Rust executable is not yet the
unified replacement for the published Python command entry point, and the
annotation schema still has documented Pydantic edge-case differences.
