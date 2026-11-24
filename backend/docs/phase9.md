# Phase 9 — model diagnosis and external validation

This document records the Phase 9 research protocol: why the registered risk
model was diagnosed, which public snapshots were added, how leakage was
controlled, what the ablation/robustness/statistical results actually were, and
which model decision followed. All numbers are projections of persisted
`validation_experiments` rows; nothing is recomputed or hard-coded in the
report or the dashboard.

## Research objectives

Phase 8 established one empirical result: on a single Brooklyn snapshot,
`risk-v1` ranked next-window 311 activity worse than the strongest count
baseline. Phase 9 asks four bounded questions without changing the registered
model:

1. **Diagnosis** — which configured factors carry signal, which are unavailable,
   and which are redundant?
2. **Ablation** — does any factor addition or removal improve paired ranking
   performance, and by how much relative to fold noise?
3. **External validity** — does the same model, metric definition, and protocol
   reproduce on other regions and periods?
4. **Robustness** — how sensitive are conclusions to H3 resolution, target
   window length, record thinning, density strata, thresholds, and missingness?

No factor weight, threshold, or configuration was changed by this phase. The
candidate variant is evaluation-only and stays `NOT_ACTIVATED`.

## Pre-registered protocol

| Item | Value |
| --- | --- |
| Protocol key | `phase9-risk-diagnosis-v1` |
| Method | multi-region rolling-origin temporal holdout with factor diagnostics, ablation, and robustness |
| Split method | `rolling_origin_temporal_holdout` |
| Evaluation unit | rolling-origin fold (8 folds per dataset) |
| Model | `risk-v1`, config hash `551e455892001c1f58198beac5c7cce3d0659edbbe6c37da36c017ff1061cb5b` |
| Target | next-window H3 activity label (any selected record) |
| Metrics | PR-AUC, ROC-AUC, precision@10, recall@10 |
| Bootstrap | percentile, 2,000 resamples, seed `20261124` |
| Sign test | exact two-sided binomial over fold wins/losses |
| Evidence kind | `EMPIRICAL_OBSERVATIONAL` |
| Development dataset | `nyc311-brooklyn-2025q1` |
| Candidate rule | highest mean paired PR-AUC delta versus full among leave-one-out variants, accepted only if the mean delta is positive |
| Activation | none; `activated = false` |

The selection rule was fixed before external datasets were evaluated. External
snapshots are labelled `external_holdout` and never inform selection, weighting,
or threshold choice.

## Datasets

All four snapshots are public NYC 311 Service Requests pulled from the fixed
Socrata resource (`https://data.cityofnewyork.us/resource/erm2-nwe9.json`) with a
deterministic query bounded by bbox, period, and the 12 selected complaint
types. Each is gzip JSON with canonical SHA-256, record count, schema version,
query metadata (including bbox and request URL), and retrieval timestamp. The
Phase 8 pipeline and normalization schema are unchanged.

| Dataset key | Role | Region bbox | Period | Records | Snapshot SHA-256 |
| --- | --- | --- | --- | ---: | --- |
| `nyc311-brooklyn-2025q1` | development | 40.680,-73.990 – 40.710,-73.950 | 2025-01-01 – 2025-03-31 | 5,102 | `bada0c22abc96c6b3d9972a206dcbfc92428faa6f19651abf857278699aee75d` |
| `nyc311-brooklyn-2025q2` | external | 40.680,-73.990 – 40.710,-73.950 | 2025-04-01 – 2025-06-30 | 3,715 | `814845ae8e04759de949f62423f0ba310ae92332a683d4cd73086dc3a331160f` |
| `nyc311-manhattan-2025q2` | external | 40.705,-73.995 – 40.745,-73.955 | 2025-04-01 – 2025-06-30 | 4,670 | `bb8bf30c3daf44a97b97330dc85710c418e418172341128737f80865cbec0ba0` |
| `nyc311-staten-island-2025q1` | external | 40.550,-74.200 – 40.640,-74.100 | 2025-01-01 – 2025-03-31 | 4,694 | `8008e5071c23ffd26ae3854b9b6d99cb052defe38b26a91cf4b628816e430142` |

Periods are non-overlapping per region, so the same query never contributes the
same record to development and external snapshots. Manhattan and Staten Island
provide genuinely different geographies; Staten Island is the only dataset
classified **SPARSE** (mean label prevalence `0.461841` across `456.75` universe
cells per fold), while the other three are **DENSE** (`0.758`–`0.769`).

Ingestion:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\ingest_nyc311.py --all
```

## Leakage controls

- History and target windows never overlap; a record inside the target window is
  never visible to the score for that origin.
- The `RiskEngine` query uses `as_of = origin`; future records exist only in the
  isolated in-memory SQLite copy used to construct labels.
- No parameter is fitted: `risk-v1` is a deterministic heuristic scoring
  function, so "training" is only the history query.
- Candidate selection runs on the development dataset only. External datasets are
  evaluated once, after selection, and are never re-run to choose a variant.
- Thresholds, resolutions, and window lengths appear only in the sensitivity
  suite; they are reported, not tuned.
- Operational incident tables are never read or mutated.
- No spatial holdout is claimed. A held-out-borough transfer protocol would
  require refitting and is listed as future work, not presented as done.

## Multi-region results

| Dataset | Role | Density | PR-AUC | ROC-AUC | P@10 | R@10 | Best baseline | Baseline PR-AUC | Δ vs best |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `nyc311-brooklyn-2025q1` | development | DENSE | 0.884367 | 0.720872 | 0.9125 | 0.114257 | `baseline_recent` | 0.907690 | −0.023323 |
| `nyc311-brooklyn-2025q2` | external | DENSE | 0.854554 | 0.661293 | 0.8625 | 0.106315 | `baseline_count` | 0.901136 | −0.046582 |
| `nyc311-manhattan-2025q2` | external | DENSE | 0.869954 | 0.688212 | 0.9000 | 0.102318 | `baseline_count` | 0.927668 | −0.057714 |
| `nyc311-staten-island-2025q1` | external | SPARSE | 0.517661 | 0.544749 | 0.6000 | 0.028502 | `baseline_count` | 0.541535 | −0.023874 |

Mean PR-AUC across datasets: `0.781634`. **CivicFlow ranks above the strongest
baseline on 0 of 4 datasets.** The deficit is consistent in sign and varies in
magnitude; on the sparse geography all models collapse toward the positive rate,
which is itself an important finding rather than a success.

Fold-level bootstrap intervals (descriptive; folds overlap in time):

| Dataset | PR-AUC mean | 95% interval |
| --- | ---: | --- |
| `nyc311-brooklyn-2025q1` | 0.884367 | 0.859091 – 0.905035 |
| `nyc311-brooklyn-2025q2` | 0.854554 | 0.822195 – 0.882060 |
| `nyc311-manhattan-2025q2` | 0.869954 | 0.841223 – 0.902702 |
| `nyc311-staten-island-2025q1` | 0.517661 | 0.490012 – 0.542887 |

## Diagnostic audit

`backend/app/validation/diagnostics.py` evaluates the nine configured factors on
the same folds without changing any score: availability, mean normalized value,
zero share, Spearman association with the target, conditional means, and pairwise
redundancy.

Recorded findings:

1. **Infrastructure and dependency factors are unavailable throughout the
   validation universe.** The isolated snapshot database has no infrastructure
   assets or dependencies, so `RiskEngine` renormalizes the remaining 20% weight.
   This is a validation-environment limitation, not evidence that those factors
   are useless in production, and it is stated that way in every report.
2. **The strongest baseline beats the registered model on every dataset.** The
   audit names the baseline method and the PR-AUC gap, so the result cannot be
   mistaken for a favourable one.
3. **The target is dense on three of four datasets** (prevalence `0.758`–`0.769`),
   which favours persistence-style baselines and inflates precision@10 relative
   to what a sparse city would show.
4. **`only_density` is the strongest single-factor variant on all four
   datasets** (`0.909089`, `0.889131`, `0.903489`, `0.523837`), i.e. a
   recency-like cell-activity density term carries most of the ranking signal.
5. Weak redundancy was observed between `category`/`severity` (0.607) and
   `active`/`density` (0.501) on the development snapshot; Staten Island reports
   a strong-redundancy hypothesis instead.

Development factor diagnostics (availability rate, target Spearman, mean
normalized value):

| Factor | Availability | Target Spearman | Mean normalized |
| --- | ---: | ---: | ---: |
| `trend` | 0.836 | 0.334 | 0.576 |
| `active` | 1.000 | 0.759 | 0.007 |
| `density` | 1.000 | 0.483 | 0.486 |
| `recency` | 1.000 | 0.279 | 0.511 |
| `spatial` | 1.000 | 0.367 | 0.717 |
| `category` | 1.000 | 0.326 | 0.658 |
| `severity` | 1.000 | 0.396 | 0.476 |
| `dependency` | 0.000 | — | — |
| `infrastructure` | 0.000 | — | — |

`trend` is the only factor that is sometimes missing (`0.836` availability). It
is also the factor the selected candidate removes. Each experiment records that
associations are descriptive, not causal.

## Factor ablation

`backend/app/validation/ablations.py` runs 19 variants on identical folds: the
full model, nine leave-one-out variants, and nine single-factor variants. Weights
are renormalized after removal so scores remain on the same scale, which also
means a variant removes both signal and weight; the report says so.

Development dataset — leave-one-out variants sorted by mean delta:

| Variant | PR-AUC | Mean Δ | 95% interval | W/L | Sign p |
| --- | ---: | ---: | --- | ---: | ---: |
| `drop_trend` | 0.890678 | +0.006311 | −0.001235 – 0.012804 | 5/3 | 0.727 |
| `drop_spatial` | 0.886437 | +0.002070 | −0.003159 – 0.007157 | 6/2 | 0.289 |
| `drop_category` | 0.885186 | +0.000819 | −0.000687 – 0.003237 | 3/5 | 0.727 |
| `drop_recency` | 0.883987 | −0.000380 | −0.009232 – 0.007283 | 5/3 | 0.727 |
| `drop_active` | 0.883256 | −0.001112 | −0.002217 – −0.000281 | 1/6 | 0.125 |
| `drop_severity` | 0.874873 | −0.009494 | −0.025089 – 0.006693 | 3/5 | 0.727 |
| `drop_density` | 0.861605 | −0.022762 | −0.032982 – −0.012787 | 0/8 | 0.008 |
| `drop_infrastructure` | 0.884367 | 0.000000 | 0.000000 – 0.000000 | 0/0 | — |
| `drop_dependency` | 0.884367 | 0.000000 | 0.000000 – 0.000000 | 0/0 | — |

`drop_infrastructure` and `drop_dependency` are exactly zero because those
factors are already absent and their weight is already renormalized — the audit
keeps them visible instead of silently dropping the rows.

Across the four datasets, **11 leave-one-out variants had a positive mean delta
and 4 had a bootstrap interval entirely above zero**: `drop_category` on
Brooklyn Q2, `drop_category` and `drop_trend` on Manhattan Q2, and
`drop_category` on Staten Island. Four intervals above zero out of 36 leave-one-out
evaluations is weak evidence after accounting for multiplicity, and the report
does not treat it as confirmation.

Single-factor variants are consistently worse than the full model except
`only_density`, which gains `+0.024722`, `+0.034577`, `+0.033535`, and
`+0.006176` respectively. That is a diagnosis of *redundancy*, not a licence to
ship a single-factor model: `only_density` drops from `0.884367` to `0.909089` on
development while losing every other factor's coverage, and it was not selected
by the pre-registered rule (which only considers leave-one-out variants).

## Robustness and sensitivity

`backend/app/validation/robustness.py` reports, without selecting anything:

- **Resolution.** H3-9 is the registered resolution. Coarser resolutions collapse
  the cell universe (development: H3-7 `6`–`7` cells, H3-8 `22`–`27`, H3-9 `86`–
  `457`), so PR-AUC rises mechanically (`0.985`–`1.000` at H3-7). These numbers
  are not comparable across resolutions and are labelled descriptive.
- **Target window.** Development: 72h `0.746736`, 168h `0.884367`, 336h
  `0.931915`, with rank overlap `0.427` and `0.531` against the registered
  window. Longer windows are easier because more cells become positive.
- **Record thinning.** Retaining 50% of records gives `0.750803`; 75% gives
  `0.837608`. Performance degrades smoothly rather than collapsing.
- **Density strata.** Development dense cells `0.952446`, sparse cells `0.692940`
  (split on median history record count, not labels).
- **Threshold bands.** Ranking is unchanged; only band counts move. Development
  at the first origin: narrow `{LOW 8, MODERATE 60, HIGH 18}`, default
  `{LOW 12, MODERATE 70, HIGH 4}`, wide `{LOW 19, MODERATE 67}`.
- **Missingness.** `descriptor` missing rate `0.000` across all four snapshots;
  `borough` missing `0.000`.

Staten Island shows the sharpest degradation: 72h `0.296628`, 168h `0.517661`,
336h `0.698408`, and resolution H3-9 `0.517661` versus H3-8 `0.901564`. Sparse
activity makes the ranking task close to the positive rate.

## Statistical uncertainty

`backend/app/validation/stats.py` computes percentile bootstrap intervals over
fold-level metrics and paired fold deltas, plus an exact two-sided sign test.
Intervals are explicitly descriptive: rolling origins overlap in time, cells are
repeated observations, and folds are not independent samples. No p-value is
presented as confirmatory.

Paired PR-AUC versus the strongest baseline:

| Dataset | Baseline | Mean Δ | 95% interval | W/L | Sign p |
| --- | --- | ---: | --- | ---: | ---: |
| Brooklyn Q1 | `baseline_recent` | −0.023322 | −0.041555 – −0.007925 | 0/8 | 0.007812 |
| Brooklyn Q2 | `baseline_count` | −0.046582 | −0.078396 – −0.018693 | 2/6 | 0.289062 |
| Manhattan Q2 | `baseline_count` | −0.057714 | −0.080486 – −0.031064 | 1/7 | 0.070312 |
| Staten Island Q1 | `baseline_count` | −0.023873 | −0.040273 – −0.009590 | 1/7 | 0.070312 |

The Δ columns differ from the paired means in the last digit because one is a
difference of pooled fold means and the other is the mean of paired fold deltas.
With 8 folds the two-sided sign test is coarse: it reaches `p = 0.0078` only when
all folds agree, `0.070` for 1/7, and `0.289` for 2/6. Only the unanimous
Brooklyn Q1 disagreement clears a conventional threshold, and even that is one
dataset among four. The report therefore leans on effect direction and interval
location rather than significance stars.

## Candidate selection and model decision

The pre-registered rule selected **`drop_trend`** on the development dataset:
mean paired delta `+0.006311`, interval `−0.001235 – 0.012804`, 5 wins / 3
losses, sign-test `p = 0.726562`. The interval includes zero, so the development
evidence alone does not establish an improvement.

External holdout evaluation of the same variant:

| Dataset | Candidate PR-AUC | Reference PR-AUC | Mean Δ | 95% interval | W/L |
| --- | ---: | ---: | ---: | --- | ---: |
| Brooklyn Q2 | 0.851006 | 0.854554 | −0.003548 | −0.011715 – 0.002846 | 4/4 |
| Manhattan Q2 | 0.877924 | 0.869954 | +0.007970 | 0.001712 – 0.015833 | 6/2 |
| Staten Island Q1 | 0.515454 | 0.517661 | −0.002207 | −0.005614 – 0.000903 | 4/4 |

**Decision: the registered model is retained unchanged.** One of three external
holdouts showed an interval above zero; two were neutral-to-negative. That is
mixed evidence, and it does not meet the bar for activation. The persisted
`RISK_ABLATION:candidate_drop_trend` row records `activated = false`, and the
report states the decision in the same words the dashboard shows.

No weights, thresholds, or configuration were modified. No model version was
published. The `risk-v1` config hash is unchanged in every experiment.

## Persistence and API

Migration `0017_phase9_diagnostics` adds `protocol_key`, `variant_key`, and
`ix_validation_experiments_protocol` to `validation_experiments`, and extends the
PostgreSQL experiment-type check with `RISK_DIAGNOSTIC`, `RISK_ABLATION`,
`RISK_ROBUSTNESS`, `RISK_GEOGRAPHIC`, and `RISK_TEMPORAL`. Rows remain
append-only.

New routes (Worker/Admin for reads, Admin for the run):

- `GET /api/v1/validation/research` — curated summary of persisted Phase 9 rows
- `GET /api/v1/validation/research/report` — 18-section research report
- `POST /api/v1/validation/research?datasets=...` — ADMIN-only, bounded runner

CLI entry points:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\run_phase9_research.py --all
.\.venv\Scripts\python.exe scripts\run_phase9_research.py --dataset nyc311-manhattan-2025q2
.\.venv\Scripts\python.exe scripts\generate_phase9_report.py --output phase9-report.json
.\.venv\Scripts\python.exe scripts\generate_phase9_report.py --strict
```

The report sections are: protocol, executive summary, Phase 8 findings,
diagnostic audit, datasets, dataset quality, methodology, split methodology,
baselines, ablation, geographic, temporal, sensitivity, statistics, model
changes, comparison, limitations, reproducibility, and future research (with
dataset count). The report is a projection of stored rows and is deterministic
apart from its generation timestamp.

## Dashboard

`/validation` keeps every Phase 8 section and adds a Phase 9 research block that
reads only persisted API data: multi-region comparison with roles and density,
diagnostic hypotheses and factor table, ablation ranking with paired deltas,
robustness/sensitivity tables, bootstrap intervals, the candidate decision,
evidence policy, limitations, and a JSON report download. Empty, loading, and
error states are explicit; the page never invents a number. The evidence chip
labels results as empirical observational complaint activity, and the dashboard
keeps the Phase 8 synthetic and simulated labels visibly separate.

## Security

- Reads are Worker/Admin; the run endpoint is ADMIN-only and bounded by dataset
  count and record caps. The CLI remains the canonical runner. External dataset
  keys are resolved against registered rows only; no caller-supplied path, URL,
  or SQL fragment reaches the snapshot loader.
- Run inputs are validated before any backtest: at most 8 dataset keys, each at
  most 200 characters, deduplicated before lookup. Oversized or excessive input
  returns `422` with `invalid_dataset_key` or `too_many_datasets`.
- Research reads load only the newest 200 protocol rows and keep the first row
  per (dataset, type, variant), so repeated append-only runs cannot make a read
  arbitrarily expensive or let an older payload shadow a newer one.
- Snapshot paths resolve only inside `backend/data/validation/`; hashes, counts,
  schema, period, and bbox are verified before use.
- No secret, service-role key, JWT, or requester identity is stored in datasets,
  experiments, or reports. No arbitrary URL fetch exists in the API.
- Append-only rows; no update/delete route. A failed run is retained as an audit
  row rather than rewritten.
- The protocol performs no model activation, dispatch, reservation, or incident
  mutation.

## Limitations

- Target labels are public 311 complaint activity, not verified hazard impact or
  municipal outcome ground truth.
- Category and severity mappings are explicit heuristics.
- Rolling origins overlap in time and cells repeat across folds, so intervals and
  sign tests are descriptive, not confirmatory.
- Infrastructure and dependency metadata are absent from the isolated validation
  database; those factors are untested here.
- Three of four datasets are dense, which favours persistence-style baselines and
  makes any-incident labels easy; the single sparse dataset shows much weaker
  ranking for every method.
- Ablation differences remove signal and weight together; renormalization changes
  the meaning of the remaining score.
- No spatial/borough transfer holdout was performed; external datasets are
  same-area temporal holdouts and cross-region replications, not a refit.
- The development candidate interval includes zero and the external holdouts are
  mixed; no superiority claim is made.

## Reproducibility

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\ingest_nyc311.py --all
.\.venv\Scripts\python.exe scripts\run_phase9_research.py --all
.\.venv\Scripts\python.exe scripts\generate_phase9_report.py --strict
```

Protocol key, bootstrap seed (`20261124`), resample count (`2000`), dataset
hashes, and the `risk-v1` config hash are stored in every experiment and repeated
in the report's reproducibility section, so a run can be audited without trusting
the dashboard.