# Phase 14 — Model Validation and Governance Status

Status: **RESEARCH_ONLY / NOT VALIDATED FOR DHAKA — operationally unavailable**

## 1. Classification

`app/models/phase14.py` defines `ModelReadinessLevel` and the constant
`DHAKA_MODEL_READINESS_LEVEL = RESEARCH_ONLY`. The descriptive endpoint
`GET /api/v1/governance/phase14/model-status` returns `RESEARCH_ONLY` with
`operationally_available: false`.

This classification is descriptive only. No Phase 14 endpoint promotes a model,
activates a model version, or authorizes civic action. `PATCH`-style mutations
of the classification do not exist.

## 2. What was inspected

- `app/risk/` — transparent, factor-based decision-support score with
  config hash, limitations, confidence and explicit "not a prediction" wording.
- `app/evaluation/engine.py` — null-safe precision/recall/F1, ROC-AUC, PR-AUC,
  Brier score, calibration error and slice metrics; returns `None` when a
  metric is undefined and `INSUFFICIENT_DATA` for small/single-class samples.
- `app/governance/service.py` — model registry with REGISTERED/ACTIVATED/
  DEACTIVATED lifecycle events, ADMIN-only activation of *model versions* for
  computational use; separate from pilot activation and from civic authority.
- `app/governance/dhaka_readiness.py` and `app/phase14/readiness.py` — require a
  persisted Dhaka geographic/temporal validation experiment with PR-AUC before
  the model-validation criterion can pass.

## 3. Dhaka evaluation requirements

| Requirement | Status |
| --- | --- |
| Dataset quality and coverage documented | NOT_ASSESSED |
| Temporal and spatial validity | NOT_ASSESSED |
| Human-verified labels | BLOCKED (0 operational records) |
| Leakage / duplicate review | NOT_ASSESSED |
| Baselines and calibration | BLOCKED (no valid Dhaka label set) |
| Metrics, error distribution, bias, uncertainty | BLOCKED (no valid Dhaka label set) |
| Reproducibility (version + training provenance) | NOT_ASSESSED for Dhaka |
| Validation provenance persisted | BLOCKED (0 Dhaka experiments with metrics) |
| NYC performance imported as Dhaka evidence | Prohibited; not done |

## 4. Operational restriction

Because no validated Dhaka label set or experiment exists, model outputs may be
used only as `EXPERIMENTAL` / `RESEARCH_ONLY` risk indicators inside a
human-supervised review queue. They are never presented as verified hazards,
ground truth, municipal decisions or authoritative prioritization.

The Phase 14 final gate keeps `phase14_model_validation` at `BLOCKED` until a
Dhaka geographic/temporal experiment with persisted PR-AUC metrics exists.
Even then the gate only permits a separate explicit activation action.

## 5. Verdict

- Model implemented: YES (decision-support scoring).
- Model validated for Dhaka: NO.
- Model approved for bounded pilot use: NO.
- Model operationally available: NO.
