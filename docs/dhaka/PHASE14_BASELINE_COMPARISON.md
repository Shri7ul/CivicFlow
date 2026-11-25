# Phase 14 — Baseline Comparison Framework

Status: **FRAMEWORK IMPLEMENTED / NO VALID DHAKA COMPARISON RESULTS**

## 1. Implemented framework

`BaselineComparison` (migration `0024`), `backend/app/phase14/baselines.py` and
`POST /api/v1/governance/phase14/baselines` persist a documented comparison with:

comparison type, method, baseline name, candidate name, label source, label
count, sample count, baseline metrics, candidate metrics, notes and limitations.
Each row is admin-created, keyed uniquely and scoped to a geographic context.

Metric keys are allow-listed (`precision`, `recall`, `f1`, `roc_auc`, `pr_auc`,
`brier_score`, `expected_calibration_error`, `false_positive_rate`,
`false_negative_rate`, `coverage`, `data_completeness`, `geographic_coverage`,
`temporal_coverage`, `human_agreement`). Numeric values must be finite; `null`
is always valid and means "not computed".

## 2. Null-protection (tested)

When `label_count == 0`, any non-null metric value is rejected with
`fabricated_metric`. A comparison with zero labels can be stored only with all
metrics null. `usable_comparisons()` ignores rows without labels, or without at
least one non-null metric on each side, so the final gate cannot pass on an
empty or invented result.

## 3. Comparison methodology (to be executed when labels exist)

1. Define the label source and verify it is human-derived, in-scope and not an
   AI prediction of the same model.
2. Freeze a candidate version and a strong baseline (municipal priority list,
   simple spatial density, rules-based priority, or temporal baseline).
3. Use identical samples and an agreed split for all methods.
4. Compute discrimination (ROC-AUC/PR-AUC where both classes exist), threshold
   metrics (precision/recall/F1/FPR), calibration (Brier/ECE), coverage and
   data/temporal completeness. Undefined metrics stay null.
5. Report disagreement with human reviewers and review time separately from
   predictive performance.
6. Record limitations and do not generalize beyond the covered slice.

## 4. Prohibited

- Calculating metrics without valid labels.
- Reporting fabricated or placeholder values.
- Treating NYC baseline results as Dhaka performance.
- Treating a synthetic fixture as a label source for operational claims.
- Claiming CivicFlow beats a baseline without a persisted, verifiable record.

## 5. Current state

| Item | Status |
| --- | --- |
| Null-safe metric engine (existing) | IMPLEMENTED / AUTOMATED-TESTED |
| Comparison record API and gate integration | IMPLEMENTED / AUTOMATED-TESTED |
| Valid Dhaka label set | BLOCKED |
| Persisted Dhaka comparison with non-null metrics | BLOCKED (0 records) |
| Human agreement / review-time measurement | NOT_ASSESSED |
