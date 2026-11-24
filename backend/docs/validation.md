# Phase 8 — real-world validation and urban data

This document records the Phase 8 dataset choice, ingestion/snapshot pipeline,
leakage controls, actual results, reproducibility commands, API, security
boundary, and limitations. Nothing here is a causal or predictive field claim.

Phase 11 adds fresh Q3 2026 Brooklyn and Manhattan slices and a separate
snapshot/provenance workspace without changing this Phase 8 protocol or its
results. See [phase11.md](phase11.md) for the fresh external validation,
reference-universe rules, real bridge integration and current readiness.

## Dataset selection

Selected dataset: **NYC 311 Service Requests** from NYC Open Data / Socrata.

- Portal: <https://opendata.cityofnewyork.us/>
- API resource: <https://data.cityofnewyork.us/resource/erm2-nwe9.json>
- Dataset key: `nyc311-brooklyn-2025q1`
- Bounded region: latitude `40.680..40.710`, longitude `-73.990..-73.950`
  (approximately 3.3 km × 3.4 km in Brooklyn).
- Period: `2025-01-01T00:00:00Z` through `2025-03-31T23:59:59Z`.
- Selected complaint types: 12 civic types mapped to ROADS, DRAINAGE,
  SANITATION, and UTILITIES.
- Retrieved and normalized records: **5,102**.
- Normalized schema: `nyc311-normalized-v1`.
- Snapshot SHA-256:
  `bada0c22abc96c6b3d9972a206dcbfc92428faa6f19651abf857278699aee75d`.

Why this source:

- Official municipal open-data publication with a documented portal and API.
- Public service-request records with stable unique keys, creation timestamps,
  complaint types, and coordinates.
- No citizen account, evidence, phone, or free-text requester identity is
  selected by this pipeline.
- Bounded enough to keep snapshots and backtests reproducible under the configured
  record and computation caps.
- Activity data supports honest spatial/temporal validation without pretending to
  be verified hazard impact, damage, or outcome ground truth.

License boundary: the Socrata resource metadata did not expose an SPDX license
field. The project therefore records the NYC Open Data portal terms and does not
assert a specific license. The exact note is stored on the dataset record and in
each report.

The selected complaint types and their category/severity mappings are explicit
heuristic adaptations in `backend/app/validation/dataset.py`. They are not
municipal severity ground truth.

## Pipeline and provenance

1. `backend/scripts/ingest_nyc311.py` fetches the fixed public Socrata query with
   a configured `validation_max_records` cap. The query is deterministic
   (`created_date,unique_key` ordering) and bounded by period, bbox, and complaint
   types.
2. Each row is validated for required fields, supported complaint type, finite
   coordinates, declared period, and declared bbox. Unsupported or invalid rows
   are rejected and counted; values are never invented.
3. Records are deduplicated by `unique_key`, sorted by
   `(observed_at, external_id)`, and hashed with canonical JSON SHA-256.
4. A gzip snapshot is written with the hash, record count, schema version, query
   metadata, source URL, license note, and rejection summary. Loading verifies the
   compressed size cap, schema version, hash, count, typed fields, period, bbox,
   and duplicate IDs.
5. The normalized batch is also sent through the existing Phase 7 ingestion
   architecture as a VERIFIED manual source with idempotent runs, provenance,
   observed timestamps, and quality snapshots.
6. The dataset is registered with source/run links, snapshot path and hash,
   period, region, schema version, license note, and reproducibility metadata.

Metadata-only dataset registration is allowed for controlled fixtures, but a
risk run against it fails with `dataset_records_unavailable` rather than
fabricating records.

Commands:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\ingest_nyc311.py --refresh
.\.venv\Scripts\python.exe scripts\ingest_nyc311.py   # reuse verified snapshot
```

## Risk backtest methodology

`backend/app/validation/risk.py` runs the **actual** `RiskEngine` against a
bounded in-memory SQLite copy of the validated snapshot. Operational incident
rows are never read or mutated.

- Rolling-origin temporal holdout with 8 folds.
- History window: 672 hours (28 days) before each origin.
- Target window: 168 hours (7 days) after each origin.
- Main H3 resolution: 9 (86 cells in this bbox at the first origin).
- Top-k: 10 cells.
- Features and model query use `as_of = origin`; future records are excluded from
  the RiskEngine query and only used to construct labels.
- Label: any selected 311 incident in the following target window for an H3 cell.
- No test-set tuning: the registered `risk-v1` configuration is used as-is. The
  validation module does not fit model parameters on the target window.

Baselines:

- **A. Incident count**: all history-window incidents per cell.
- **B. Recent count**: incidents in the 168 hours before the origin.
- **C. Weighted count**: category, severity, and recency-weighted history count.
- **D. Persistence**: previous target-window count.

Metrics: precision@10, recall@10, ROC-AUC (average-rank Mann–Whitney with ties),
and average precision (PR-AUC).

## Actual results

Source: persisted experiment `risk_backtest-0360bfe9-d873-4a2e-aed6-eccad3eb42af`,
8/8 completed folds. Model `risk-v1`, config hash
`551e455892001c1f58198beac5c7cce3d0659edbbe6c37da36c017ff1061cb5b`.

| Method | PR-AUC | ROC-AUC | Precision@10 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| CivicFlow risk | 0.884367 | 0.720872 | 0.912500 | 0.114257 |
| Baseline A — count | 0.905122 | 0.774194 | 0.937500 | 0.117226 |
| Baseline B — recent | 0.907690 | 0.741687 | 0.962500 | 0.120454 |
| Baseline C — weighted | 0.906120 | 0.745368 | 0.975000 | 0.121909 |
| Baseline D — persistence | 0.907690 | 0.741687 | 0.962500 | 0.120454 |

**Honest conclusion:** CivicFlow did not outperform the strongest baseline
(`baseline_recent`). Its mean PR-AUC was lower by `0.023323`; the persisted
finding says so explicitly. This is an unfavorable empirical result, retained
rather than hidden. High precision@10 alongside low recall@10 reflects a dense
target (many H3 cells have future activity) and a small top-k relative to the
number of positive cells.

Sensitivity at the first origin (descriptive diagnostics, not model selection):

- 168h vs 336h: Spearman `0.882178`, top-20 Jaccard `0.600000`, 86 common cells.
- H3 cell counts: resolution 7 = 6, resolution 8 = 22, resolution 9 = 86.
- Maximum score by resolution: 7 = 62.84, 8 = 64.05, 9 = 68.36.
- Top-20 Jaccard, H3-7 vs H3-8 parent: `1.000000`.
- Cells at/above configured bands: low 86, moderate 74, high 4, critical 0.
- Density diagnostics: mean target prevalence `0.758496` across a mean 105.625
  universe cells and 372.125 target records per fold; classified **DENSE**.
  Mean history records per fold: 1,620. A sparse synthetic test exercises the
  same path without changing the empirical record.

Resolution 9 and top-k 10 were selected to obtain enough cells for meaningful
ranking in the bounded bbox; resolution 8 had only 22 cells and made top-20
effectively exhaustive. This is a design choice, not tuning against reported
metrics, and it is recorded in each experiment.

## Synthetic correlation validation

No labelled municipal duplicate ground truth exists in the selected dataset.
`backend/app/validation/correlation.py` therefore uses 8 hand-constructed,
explicitly labelled synthetic cases through the real Phase 4
`_score_candidate` function.

Actual result: 4 true positives, 1 false positive, 3 true negatives, 0 false
negatives; precision `0.8`, recall `1.0`, F1 `0.888889`.

This is synthetic fixture evidence only. It is never presented as field
precision/recall. Suggestions remain human-review only; nothing is auto-merged
or mutated.

## Decision simulation validation

`backend/app/validation/decision.py` runs a bounded, explicitly synthetic
planning scenario through the real Phase 6 `compare_strategies` function across
all four strategies. Inputs include available, limited, and UNKNOWN resources,
dependencies, budget, horizon, and synthetic target risk cells.

Actual result with the active `decision-v1` configuration (config hash
`dffbc2bdf0ca2abf0027c064971005de`): BOUNDED comparison winner
`COST_EFFICIENT`, planned reduction 22 versus 21 for the other strategies. The
schedule is run twice and is deterministic across those runs. UNKNOWN equipment cannot be silently treated as
available. No dispatch, reservation, assignment, resource decrement, or incident
mutation occurs.

Evidence is labelled `SIMULATED_PLANNING`; expected reductions and availability
are planning assumptions, not observed outcomes.

## Persistence and reports

Two staff-only tables are added by `0016_validation_workspace`:

- `validation_datasets` — source/run links, immutable snapshot hash/path,
  period, region, schema, license, record count, status, metadata.
- `validation_experiments` — append-only experiment key, type, evidence kind,
  method/split, model/config provenance, metrics, baselines, findings,
  limitations, reproducibility, status, timestamps, and error summary.

Run keys are unique. New runs create new rows and never overwrite prior results.
Reports are assembled from the stored experiment and dataset rows.

Commands:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\generate_validation_report.py --latest
.\.venv\Scripts\python.exe scripts\generate_validation_report.py --all --output validation-report.md
.\.venv\Scripts\python.exe scripts\generate_validation_report.py --json
```

## API

All routes require an authenticated Worker or Admin; dataset creation is
ADMIN-only.

- `GET /api/v1/validation/overview`
- `GET /api/v1/validation/datasets`
- `POST /api/v1/validation/datasets` (ADMIN)
- `GET /api/v1/validation/datasets/{id}`
- `GET /api/v1/validation/experiments?limit=...`
- `GET /api/v1/validation/experiments/{id}`
- `GET /api/v1/validation/experiments/{id}/report`
- `POST /api/v1/validation/experiments/risk/{dataset_id}`
- `POST /api/v1/validation/experiments/correlation`
- `POST /api/v1/validation/experiments/decision`

The `/validation` frontend route renders persisted dataset provenance, baseline
comparison, sensitivity, synthetic evidence labels, limitations, and report
downloads. No dashboard statistic is mocked.

## Security

- Worker/Admin RBAC is enforced in FastAPI; dataset registration is ADMIN-only.
- RLS on both validation tables is staff-only (`is_worker_or_admin()`), with
  `authenticated` SELECT only. Direct Citizen PostgREST reads returned `[]` in
  live validation.
- Snapshot paths must resolve inside `backend/data/validation/`; arbitrary paths
  and oversized snapshots are rejected. Snapshot hashes and counts are verified
  before use.
- No requester name, phone, email, address, or account fields are selected or
  stored by the validation pipeline. Coordinates are 311 complaint locations at
  the selected public precision, not citizen account data.
- The API does not fetch arbitrary URLs. The external fetch exists only in the
  fixed-URL CLI ingestion path.
- No service-role key, JWT, or secret is written to datasets, experiments,
  reports, or frontend code.
- No destructive database operation, live downgrade, dispatch, reservation, or
  incident mutation is part of Phase 8.

## Limitations

- Target labels are public 311 complaint activity, not verified hazard impact or
  municipal ground truth.
- Complaint-type → category/severity mappings are heuristic.
- The bounded bbox and 12-type selection are not citywide coverage.
- Dense activity and a small H3 universe make any-incident labels easy; metrics
  must not be generalized to sparse cities or operational outcomes.
- The isolated validation SQLite copy has no infrastructure assets/dependencies,
  so those risk factors are excluded.
- CivicFlow underperformed the strongest baseline on this slice; no claim of
  superiority is made.
- Correlation metrics are synthetic fixtures, not field labels.
- Decision reductions and resource availability are planning assumptions.
- Single-region, single-quarter evidence is not external validity.
