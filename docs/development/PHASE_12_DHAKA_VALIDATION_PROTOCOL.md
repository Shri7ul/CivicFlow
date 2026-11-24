# Phase 12 — Dhaka Model Validation and Research Protocol

**Status:** PROTOCOL PREPARED; EVALUATION BLOCKED; NO MODEL ACTIVATION
**Date:** 2026-11-25

## 1. Scope

This document prepares the existing risk evaluation framework for a future
Dhaka-specific external validation. It **does not** train, tune, promote or
activate any model. NYC results remain NYC results and are never used as Dhaka
performance evidence. The active model registry was not modified.

## 2. Review of the existing prediction target

| Item | Current design | Dhaka suitability assessment |
| --- | --- | --- |
| Incident definition | Public 311 complaint activity mapped to `IncidentCategory` | NOT_ASSESSED: no verified Dhaka complaint taxonomy or reporting channel established |
| Target definition | Complaint occurrence within H3 cell/time window | Proxy for reported issues, not verified hazard impact; unsuitable as operational truth without Dhaka labels |
| Geographic unit | H3 cells (existing engine resolution) | NOT_ASSESSED: resolution must be re-justified for Dhaka density and sparse data |
| Temporal windows | Quarterly research slices for NYC | NOT_ASSESSED: Dhaka reporting cadence and seasonality (monsoon) unknown |
| Data sparsity | Low in sparse NYC slices | Expected to be high for any small Dhaka cell; needs explicit minimum counts |
| Urban density | NYC grid | Dhaka density differs; distance/H3 neighbourhood priors may not transfer |
| Label reliability | Complaint status is not verified impact | Same limitation applies; ground-truth protocol required |
| Missingness | Borough missingness tracked in NYC | Dhaka has no equivalent field; new missingness schema required |
| Geographic bias | Borough-based slices | Ward/corporation bias likely; boundaries not acquired |
| Data collection bias | 311 usage patterns | Different reporting channels and access in Dhaka |
| Reporting bias | Self-selected complaints | Likely stronger and unmeasured in Dhaka |
| Temporal leakage | Rolling-origin backtests in Phase 9 | Must be re-checked for any Dhaka time split |
| Spatial leakage | H3 neighbourhood overlap | Must be re-checked with a geographic holdout; adjacent cells must not cross splits |
| Baselines | Phase 9 strongest baseline | Baseline suitability for Dhaka is NOT_ASSESSED; recompute on Dhaka data only |
| Metrics | PR-AUC, ROC-AUC, Precision@k, Recall@k, calibration | All require Dhaka labels; none may be reported yet |

## 3. Required external validation design (future)

1. **Geographic holdout.** Hold out an entire contiguous area (e.g. a set of
   wards/cells) so adjacent H3 cells cannot leak across train/test. The holdout
   cannot be an NYC slice.
2. **Temporal holdout.** Rolling-origin split with a gap; no overlap between
   training features and the evaluation period.
3. **Baselines.** Recompute the strongest baseline on the same Dhaka slice,
   with the same candidate universe and metric definition. NYC baseline numbers
   are not transferable.
4. **Metrics.** PR-AUC (primary for imbalance), ROC-AUC, Precision@k and
   Recall@k at declared k, calibration where score distributions support it.
5. **Data quality report.** Record counts, rejected counts, missingness by
   field, coordinate validation, provenance and geographic coverage.
6. **Error analysis.** False positives/negatives by category, area and time;
   distinguish reporting artefacts from model errors.
7. **Robustness.** Re-run with alternate cell resolution, time window and
   threshold; report sensitivity, not a single favourable configuration.
8. **Confidence intervals.** Bootstrap only when the sample is large enough
   and the reference universe is complete; otherwise report counts and
   uncertainty qualitatively.
9. **Sampling limitations.** State sampling fraction, seed and known biases.
10. **Geographic distribution.** Coverage by ward/corporation and unmapped
    areas; no population estimates unless sourced.
11. **Reproducibility.** Pinned dataset keys, hashes, code version, config hash,
    and an append-only experiment event. Use existing
    `ValidationExperimentType.RISK_GEOGRAPHIC` / `RISK_TEMPORAL` labels.

## 4. Hard blockers

- No Dhaka complaint/incident dataset registered.
- No human-verified Dhaka ground truth.
- No complete Dhaka correlation reference universe.
- No authoritative boundary or defensible geographic holdout.
- No verified baseline comparison on Dhaka data.

Therefore Dhaka model validation is **BLOCKED**. No performance metric is
invented and no superiority claim is made.

## 5. Governance boundary

Phase 12 prepared evaluation interfaces and readiness views only. There was no
model training run, no hyperparameter tuning, no promotion, no activation, and
no change to `ModelVersion.is_active`. Any future activation requires separate
governance approval under the existing pilot transition rules.

## 6. Exit status

- `IMPLEMENTED`: validation protocol, context-aware experiment filtering in
  Dhaka readiness.
- `BLOCKED`: actual Dhaka evaluation, baseline comparison, metric reporting.
- `NOT_ASSESSED`: target suitability, H3 resolution, calibration, confidence
  intervals, sampling plan.
