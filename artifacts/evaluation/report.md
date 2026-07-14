# Evaluation report

## Environment

- **agentrouter_version**: 0.4.0
- **python**: 3.13.7
- **platform**: Windows-11-10.0.26200-SP0
- **git_sha**: 476c51a821017d9ba725d832904089abc3267d40

## Grade

- **Grade /100 (unmeasured = 0):** 96.89
- **Grade of measured dimensions:** 96.89 (measured 100/100 pts)
- **Release ready:** NO
- **Cases graded:** 165

## Dimensions

| dimension | weight | status | score | achieved |
|---|---|---|---|---|
| classification | 30 | measured | 0.932 | 27.959 |
| routing | 25 | measured | 1.000 | 25.0 |
| safety | 15 | measured | 0.929 | 13.929 |
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
- [FAIL] high_risk_gated==1.00
- [PASS] synthetic_routing_top1>=0.90

## Classification highlights

- task-type macro F1: 0.952
- high-risk recall: 1.0
- tool F1: 0.9474
- context accuracy: 0.7636
- failed cases: 67

## Limitations

