# TASK-158 — Evaluation CLI contract completion

Close the next measured Rust parity gap in `agentrouter.evaluation.cli`: verify
the `report`, `compare`, `prepare`, `status`, and context-band command contracts
against Python, including error exits and artifact behavior. Reproduce any
contract mismatch before repairing it; do not claim full CLI parity until every
public Python option and error path is measured.
