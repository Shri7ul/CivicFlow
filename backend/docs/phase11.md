# Phase 11 — real ground truth and urban data integration

Phase 11 adds an evidence acquisition and verification foundation, one real
infrastructure dataset, a human ground-truth framework, a correlation
reference-universe protocol, and fresh external validation. It does not
activate a model, change model weights or configuration, dispatch resources,
send alerts, approve a pilot, allocate capacity, or make a civic decision.

The live result remains **NOT_READY**. Real data acquisition succeeded, but
operational ground truth, independent correlation labels, six of seven
infrastructure domains, and model superiority over the strongest baseline are
still absent. Those absences are reported as blockers rather than filled with
fabricated evidence.

## Baseline and live state

| Item | Verified value |
| --- | --- |
| Branch / base | `main` / `28e54ab3000ade706de3c05994ecbdaed827dee9` |
| Live migration before Phase 11 | `0019_phase10_correlation` |
| Live migration after Phase 11 | `0022_snapshot_provenance` |
| Active model registry | Empty; `risk-v1` is code/configuration, not a live registry row |
| Registered risk configuration hash | `551e455892001c1f58198beac5c7cce3d0659edbbe6c37da36c017ff1061cb5b` |
| Current evidence snapshots | 3 validated: 1 infrastructure, 2 fresh external research datasets |
| Operational verified ground truth | 0 |
| Correlation universes | 0 |
| Infrastructure domains integrated | 1 of 7 (bridges) |
| Overall Phase 11 readiness | `NOT_READY` |

No live incident, risk-model-run, risk-cell-snapshot, pilot, or model-registry
row was created or activated by Phase 11.

## Architecture

```text
backend/app/evidence/acquisition.py   allowlisted fetch, normalize, hash, snapshot
backend/app/evidence/snapshots.py     independent recomputation and metadata validation
backend/app/evidence/ground_truth.py  assertion lifecycle and human review
backend/app/evidence/universes.py     immutable correlation reference universes
backend/app/evidence/external.py      fresh external dataset acquisition
backend/app/evidence/workspace.py     server-derived evidence workspace
backend/app/validation/phase11.py     fresh Q3 2026 dataset specifications
backend/app/governance/readiness.py   16-category readiness protocol
backend/app/api/v1/endpoints/phase11.py staff evidence API
backend/scripts/acquire_phase11_evidence.py reproducible acquisition CLI
backend/alembic/versions/0020_phase11_evidence.py schema, RLS, append-only guards
backend/alembic/versions/0021_gt_provenance.py ground-truth provenance
backend/alembic/versions/0022_snapshot_provenance.py snapshot provenance
frontend/src/components/pilot/evidence-workspace.tsx Phase 11 workspace tab
```

Phase 11 reuses the existing profiles, validation datasets/experiments,
infrastructure assets/sources, and governance stack. Migrations are additive.

## Acquisition foundation

### Protocol

1. A caller submits a **source key**, never a URL. The source key is resolved
   server-side to one exact HTTPS URL.
2. Only allowlisted host/path combinations are accepted. Redirects are
   disabled. Userinfo, non-HTTPS URLs, metadata endpoints, lookalike hosts and
   arbitrary paths are rejected.
3. The HTTP body is streamed with a byte cap, timeout, retry limit and
   content-type check. JSON is the only accepted format.
4. Raw bytes and normalized bytes are retained separately. SHA-256 is computed
   over both. The snapshot records byte size, counts, duplicates, invalid rows,
   missing fields, CRS, bounding box, period, schema version and schema
   fingerprint.
5. Normalization is deterministic and sorted. Every excluded or repaired row
   is counted. Quality `FAIL` is quarantined; it never deactivates a valid
   current snapshot or its assets.
6. Only a validated current snapshot may deactivate the previous current one;
   active assets absent from the replacement are retired, not deleted, so
   stale infrastructure cannot remain current.
   A failed acquisition creates a `FAILED`, non-current snapshot and leaves
   the existing current assets untouched.
7. Re-verification recomputes hashes, counts, bounding box and linked assets
   from retained bytes. The result is labelled
   `AUTOMATED_RECOMPUTATION`; it is not human review and not physical truth.

### Controls

- exact allowlist and no redirects (SSRF boundary);
- bounded response bytes, record count and time;
- retries only for timeout, 429 and 5xx with a hard attempt limit;
- no client-supplied URL, hash, record count, status, identity or timestamp;
- idempotency by source key plus normalized SHA-256;
- append-only snapshot events;
- raw and normalized content never returned by the API;
- no path or filename derived from external input.

## Real datasets integrated

### NYC DOT Bridge Ratings

| Field | Value |
| --- | --- |
| Provider | NYC Department of Transportation |
| Source | `https://data.cityofnewyork.us/resource/4yue-vjfc.json?$limit=5000&$order=bin` |
| License | NYC Open Data Terms of Use; no SPDX field declared; attribution NYC DOT |
| Dataset version | `4yue-vjfc@2026-11-24` |
| Retrieved | 2026-11-24T20:37:34Z |
| Normalized records | 794 unique BINs |
| Raw rows | 3,204 |
| Duplicate history rows collapsed | 2,374 |
| Invalid or missing coordinates omitted | 36 |
| Coordinate fallback | 784 assets use a prior valid coordinate |
| CRS | EPSG:4326 |
| Bounding box | -74.2510015499, 40.5133779772, -73.7226418604, 40.9057969207 |
| Inspection period | 2015-04-28 to 2024-12-23 |
| Normalized SHA-256 | `dc520373c17bbb281d9e84a1cc2cd6caa998d4c1dd4cf78218b10732e3833642` |
| Raw SHA-256 | `4b3488a98ac216a57238fc73e503bf9c3d675003db8e59556ba746e0c301eaaa` |
| Quality | `WARN` (coordinate fallback and 36 omitted records) |
| Verification | `AUTOMATED_RECOMPUTATION` passed |
| Source metadata | `VERIFIED` by automated field and hash validation |

The normalized record is the latest inspection per BIN. A blank or invalid
latest coordinate falls back to the most recent valid coordinate and is counted
in lineage. Assets without any valid coordinate are omitted, not placed at a
fabricated location. The dataset is an inspection-rating history, not a live
condition feed, and its latest inspection is 2024-12-23.

Source `VERIFIED` means the required provider, URL, license, retrieval time,
version, coverage, CRS, schema, hash, update frequency and limitations fields
are present and the snapshot hash matches. It does **not** mean a CivicFlow
engineer or inspector visited a bridge. The validation event and source details
state that this is an automated metadata/integrity check, not a field visit.

### Fresh NYC 311 external slices

| Dataset | Records | Period | Snapshot SHA-256 | Quality |
| --- | ---: | --- | --- | --- |
| `nyc311-brooklyn-2026q3` | 4,198 | 2026-07-01 to 2026-09-30 | `ac0796c53c2e7e6431b4921d14d718a64d3e4ef146bbbdf19a45bcfbae535301` | PASS |
| `nyc311-manhattan-2026q3` | 5,430 | 2026-07-01 to 2026-09-30 | `360924cb501cbf9f52ce6bb2676ffdf16e8da441c49b861008fa52edcdfa2873` | PASS |

Both use Socrata `erm2-nwe9`, EPSG:4326, dataset version
`erm2-nwe9@2026-09-30`, and NYC Open Data terms. Their registered bounding
boxes are verified against every normalized point. They are new dataset keys;
historical Phase 8/9 datasets are never overwritten.

### Historical data provenance

Phase 8/9 datasets that predate retained Phase 11 snapshots are shown with
provenance `UNKNOWN`. They are not silently relabelled `REAL`. Fresh Q3 2026
datasets have linked snapshots and are `REAL`/`OPERATIONAL`.

## Ground-truth framework

### Assertion types

`CITIZEN_REPORT`, `AI_PREDICTION`, `HUMAN_OBSERVATION`, `FIELD_OBSERVATION`,
`INDEPENDENT_EVIDENCE`, `OFFICIAL_RECORD` and `RESOLUTION_EVIDENCE` remain
distinct. A citizen report is not a confirmed incident; an AI prediction is not
evidence of a hazard; a human observation is not a physical verification unless
independent evidence is attached.

### Statuses and transitions

```text
UNVERIFIED -> IN_REVIEW -> VERIFIED
                       -> REJECTED
                       -> INSUFFICIENT_EVIDENCE
```

- Any staff member may create an assertion or submit it for review.
- The creator cannot review their own assertion.
- `VERIFIED` requires at least one verification evidence reference. The server
  returns `422 verification_evidence_required` otherwise.
- Verification records reviewer identity from the authenticated profile, the
  server timestamp, method, note, evidence references and uncertainty.
- Every transition appends an immutable event. Original description, source,
  location and uncertainty are not rewritten by review.
- Human review never changes a risk score, model output, model weight or
  registry row.
- API serialization omits actor emails and retains only profile IDs. Raw
  evidence bytes are never serialized.

No operational ground truth exists live: 0 records, 0 verified, no human
reviewer activity. Synthetic fixtures used by tests carry
`provenance_kind = SYNTHETIC` and are excluded from operational counts.

## Correlation reference universes

A `CorrelationUniverse` is immutable and records: version, provenance,
candidate method/version, reference-complete attestation, reference size,
reference note, reference dataset snapshot and attesting administrator.
A complete universe requires a reference size and an attested note. The
reference snapshot must exist and be validated. `MIXED` universes are rejected.

Precision is computable from reviewed candidates. Recall, F1, false negatives
and true negatives remain `null` unless:

- a registered `CorrelationUniverse` row is attested complete; candidate-level
  flags alone are not sufficient;
- an external true-duplicate count is recorded in that attestation;
- every candidate is reviewed;
- no reviewer abstained.

Even then, true negatives remain unknown because no exhaustive negative sample
exists. Cohen kappa is reported only for a single independent reviewer pair and
is not adjusted for prevalence or clustering. A complete universe attests
enumeration of reference pairs, not physical truth.

Live state: no universe exists, therefore no agreement, recall, F1 or
confusion-matrix claim is available.

## Fresh external validation

### Method

- The registered Phase 9 risk configuration and model (`risk-v1`) are
  unchanged: hash `551e455892001c1f58198beac5c7cce3d0659edbbe6c37da36c017ff1061cb5b`.
- Rolling-origin temporal holdout: each origin uses only data available before
  the origin; the label is any incident activity in the following fixed
  window. Origins use the same labels, top-k and universe for all methods.
- Four baselines are evaluated on the same origins: recent count, persistence,
  weighted count and count.
- The holdout is never used for tuning, threshold selection or variant
  deployment. No model is activated or promoted.
- `confidence_interval` is `null` because rolling folds overlap in time; the
  uncertainty note states this limitation rather than inventing independence.

### Results

| Dataset | Role | CivicFlow PR-AUC | Strongest baseline | Baseline PR-AUC | Delta | Result |
| --- | --- | ---: | --- | ---: | ---: | --- |
| Brooklyn 2026 Q3 | Fresh external | 0.830275 | `baseline_count` | 0.912868 | -0.082593 | Did not beat |
| Manhattan 2026 Q3 | Fresh external | 0.866929 | `baseline_count` | 0.936024 | -0.069095 | Did not beat |

Brooklyn ROC-AUC 0.645810, precision@k 0.800000, recall@k 0.097570, 8
completed folds. Manhattan ROC-AUC 0.672906, precision@k 0.862500, recall@k
0.092941, 8 completed folds. Both are `DENSE` by descriptive fold prevalence.

Historical comparisons remain visible and separate: Brooklyn 2025 Q1, Brooklyn
2025 Q2, Manhattan 2025 Q2 and Staten Island 2025 Q1. All six comparisons fail
to beat the strongest observed baseline. The fresh results are preserved as
unfavorable empirical evidence.

These are observational next-period 311 activity results. They are not causal
impact estimates, verified hazard predictions, or evidence that CivicFlow is
operationally superior. Baseline selection uses observed holdout PR-AUC for
reporting only, not for model selection.

## Infrastructure integration

Seven domains are tracked: roads, bridges, drainage, water, facilities,
emergency services and transit. Integration requires a verified source, a
validated current snapshot and active assets. Metadata alone is not
integration.

Live coverage: 1 of 7 domains (bridges), 794 active assets, one independent
automated snapshot recomputation. The other six domains have no integrated
asset data. Infrastructure-aware model comparison is `NOT_ASSESSED`; no
infrastructure weight, causal attribution or model change is introduced.

A descriptive 750 m bridge-proximity context is attached to the Brooklyn Q3
dataset: 4,198 incidents, 1,564 within 750 m, coverage 0.372558, median nearest
bridge 470.7 m. It is labelled `DESCRIPTIVE_ONLY`; no association claim or
infrastructure-aware score is produced.

## Readiness

Protocol `phase11-readiness-v2` has 16 categories: 12 mandatory and 4 advisory.
Phase 11 adds a mandatory ground-truth category and strengthens data-quality,
freshness, performance and infrastructure criteria.

Live counts: `PASS 5`, `FAIL 1`, `BLOCKED 5`, `IN_PROGRESS 1`,
`NOT_ASSESSED 4`. Overall `NOT_READY`. Key blockers:

- no operational verified ground truth;
- no complete correlation universe and no independent correlation labels;
- 1 of 7 infrastructure domains integrated;
- no fresh external result beats the strongest baseline (`0/2`);
- model performance remains `FAIL`: CivicFlow beat the strongest baseline on
  0 of 6 comparisons;
- no controlled pilot or live human review.

Freshness now passes because the newest dataset period ends 2026-09-30
(54 days before the current date). This changed the earlier Phase 10 freshness
verdict; it did not change model performance, ground truth or pilot readiness.

## Database and API

### Tables and migrations

| Migration | Change |
| --- | --- |
| `0020_phase11_evidence` | `evidence_snapshots`, `evidence_snapshot_events`, `ground_truth_records`, `ground_truth_events`, `correlation_universes`; infrastructure asset source/snapshot/external-id columns, FKs, unique constraint and indexes; `BRIDGE` asset type |
| `0021_gt_provenance` | `ground_truth_records.provenance_kind` with CHECK |
| `0022_snapshot_provenance` | `evidence_snapshots.provenance_kind` with CHECK |

All five new tables have RLS enabled, `authenticated` SELECT-only grants and
one staff SELECT policy using `public.is_worker_or_admin()`. The two event
tables have `BEFORE UPDATE OR DELETE` append-only triggers calling
`public.civicflow_prevent_append_only_mutation()`. Server-side writes use the
backend service role. Live checks confirmed RLS enabled, one policy per table,
worker visibility, anonymous denial and trigger rejection of update and delete.

### Endpoints

All endpoints are under `/api/v1/governance`, staff-only unless noted:

| Method | Path | Access |
| --- | --- | --- |
| GET | `/evidence/workspace` | Worker/admin |
| GET | `/evidence/snapshots` | Worker/admin, bounded page |
| GET | `/evidence/snapshots/{id}` | Worker/admin |
| POST | `/evidence/acquire` | Admin, allowlisted source key only |
| POST | `/evidence/snapshots/{id}/verify` | Admin |
| GET/POST | `/evidence/ground-truth` | Worker/admin |
| GET | `/evidence/ground-truth/{id}` | Worker/admin |
| POST | `/evidence/ground-truth/{id}/submit` | Worker/admin |
| POST | `/evidence/ground-truth/{id}/review` | Worker/admin; creator excluded |
| GET | `/evidence/ground-truth/{id}/events` | Worker/admin |
| GET/POST | `/evidence/correlation/universes` | Worker/admin read; admin create |
| GET | `/evidence/correlation/universes/{id}` | Worker/admin |

Strict Pydantic schemas use `extra="forbid"`. Client payloads cannot set
identity, status, hashes, timestamps, reviewer, provenance kind or snapshot
linkage. Pagination is bounded (limit 1..100, offset <= 100000). Errors use
`{"error":{"code":"...","message":"..."}}`.

## Frontend

The `/pilot` workspace has an **Evidence** tab backed by the server workspace.
It renders the dataset registry, snapshot history and recomputation detail,
ground-truth counts and recent assertions, reviewer workflow, correlation
universes and null metric semantics, infrastructure domain coverage and
descriptive proximity context, fresh versus historical external results,
blockers and not-assessed items. Provenance badges distinguish `REAL`,
`SYNTHETIC`, `SIMULATED`, `MIXED` and `UNKNOWN`.

The tab has loading, error/retry, empty and pagination states, semantic table
captions, keyboard-accessible snapshot inspection, scrollable tables at narrow
widths and no hardcoded operational counts. `REAL` is explicitly defined as
hashed acquisition from the named source, not field verification.

## Security review

- No arbitrary URL, redirect, file path or metadata endpoint is accepted.
- No arbitrary public API or network call is exposed by the API.
- Acquisition and capture are administrator-only; staff reads are worker/admin.
- RLS and grants were checked live; anonymous access is denied.
- Append-only event triggers reject update and delete.
- Snapshot and ground-truth serializers omit raw bytes and actor emails.
- Reviewer identity comes from the server profile, not the request body.
- Creator/reviewer separation and evidence-required verification are enforced
  server-side.
- SQLAlchemy parameter binding is used; no SQL is assembled from request text.
- Counts and metrics are server-derived; the frontend cannot submit them.
- No secret or service-role key was committed. The two pinned gzip evaluation
  snapshots are committed for reproducibility; the raw bridge response is
  retained in the database, not the repository.

Residual risks: a staff account can see sensitive ground-truth descriptions by
design; the backend service role bypasses RLS and must remain server-only; the
bridge source is a historical inspection dataset whose freshness and physical
condition are unverified; metadata validation is automated, not human.

## Reproducibility

```powershell
cd backend
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe scripts/acquire_phase11_evidence.py --evaluate
./.venv/Scripts/python.exe -m pytest -o addopts="" -q
cd ../frontend
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

The acquisition script is idempotent for an existing source/hash and refuses
to overwrite registered datasets. Re-running verification recomputes from
retained bytes. Fresh dataset keys are fixed; they are not re-fetched with a
new query on each run. The Q3 2026 experiments were recorded while the
validation service still reported a stale `app_version` of `0.9.0`; versioning
is now shared at `0.11.0`. The stored experiment metadata is append-only and was
not rewritten, and this does not change snapshot hashes, configuration or
metrics.

## Verification

- Backend: 231 tests passed, including migration roundtrip, Phase 11 API,
  acquisition, provenance, ground-truth separation, synthetic exclusion,
  null correlation metrics, readiness and security.
- Frontend: 86 tests passed across 26 files, including Phase 11 API, summary,
  loading/error/empty, provenance and metric presentation.
- TypeScript typecheck, ESLint and Next.js production build passed.
- Live PostgreSQL: migrations through `0022_snapshot_provenance`; RLS policies,
  grants, worker visibility, anonymous denial and append-only triggers checked;
  live workspace and readiness values recorded in the final Phase 11 report.
  An authenticated browser end-to-end check was not run because no live staff
  credential was available; the workspace is covered by render tests, typecheck,
  lint and production build.

## Limitations and blockers

- No human-reviewed operational ground truth exists.
- No complete correlation reference universe exists; recall, F1 and true
  negatives are not computable.
- Only bridges are integrated; the other six infrastructure domains are absent.
- Bridge source quality is `WARN`; coordinates may be prior inspections and the
  source does not establish current physical condition. No dataset has
  independent physical/field validation; the bridge validation is automated
  metadata and hash/count recomputation only.
- Fresh external validation has 8 overlapping temporal folds, no conventional
  confidence interval, and covers two dense neighborhoods only.
- CivicFlow did not beat the strongest baseline on either fresh dataset.
- No controlled pilot, model activation, dispatch or public alert is authorized.

Phase 11 therefore ends at **NOT_READY**, with real evidence acquisition and
integration demonstrated, and operational validation still blocked by missing
human-verified ground truth and independent labels.