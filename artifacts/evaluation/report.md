# Evaluation report

## Environment

- **agentrouter_version**: 0.4.0
- **python**: 3.13.7
- **platform**: Windows-11-10.0.26200-SP0
- **git_sha**: 602321af91ff298c0d5b59d6d36c24f845557fc1
- **git_dirty**: True
- **classifier_sha256**: c7fc8445d42c01eb6f1f4b9a0a17f6c918288564a84466c26d3f187474154c55

## Grade

- **Grade /100 (unmeasured = 0):** 98.23
- **Grade of measured dimensions:** 98.23 (measured 100/100 pts)
- **Release ready:** NO
- **Cases graded:** 165

## Dimensions

| dimension | weight | status | score | achieved |
|---|---|---|---|---|
| classification | 30 | measured | 0.941 | 28.226 |
| routing | 25 | measured | 1.000 | 25.0 |
| safety | 15 | measured | 1.000 | 15.0 |
| cli_platform | 10 | measured | 1.000 | 10.0 |
| provider_registry | 8 | measured | 1.000 | 8.0 |
| feedback_storage | 7 | measured | 1.000 | 7.0 |
| performance | 5 | measured | 1.000 | 5.0 |

## Release gates

- [PASS] task_type_macro_f1>=0.90
- [PASS] high_risk_recall==1.00
- [PASS] approval_accuracy==1.00
- [PASS] tool_needs_f1>=0.90
- [FAIL] context_band_accuracy>=0.90
- [PASS] high_risk_gated==1.00
- [PASS] synthetic_routing_top1>=0.95

## Classification highlights

- task-type macro F1: 0.952
- high-risk recall: 1.0
- tool F1: 0.9474
- gold-set context accuracy (in-sample): 0.897
- failed cases: 49

## Context-band generalization (frozen final holdout)

- holdout checksum: `ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f`
- current accuracy: 0.6667 (95% CI [0.5207, 0.7864])
- current macro-F1: 0.6792 (bootstrap 95% CI [0.5351, 0.8031])
- per-band recall: {'small': 0.7333, 'medium': 0.6, 'large': 0.6667}
- pre-TASK-004 accuracy: 0.4889
- accuracy delta: 0.1778

## Limitations

- The holdout is public and model-assisted, pending independent human review.
- Context-band labels infer required input size from short prompts without real files.
- Confidence intervals quantify sample uncertainty, not annotation uncertainty.
