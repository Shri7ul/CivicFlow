# Phase 7 — operational maturity and intelligence validation

Phase 7 makes CivicFlow's risk and planning outputs governable and observable. It
adds model registration/evaluation, source provenance and freshness, staff
alerts, in-app notifications, and human plan review. It deliberately does **not**
add dispatch, resource execution, incident mutation, or automated approvals.

## Architecture

```text
risk/decision runtime settings ──> model_versions ──> model_evaluations
                                      │
                                      └── model_version_events (activation audit)

data_sources ──> ingestion_runs ──> ingested_records
      │                │
      └──> data_quality_snapshots ──> /operations/quality, /risk/data-quality

alert_rules ──> alerts ──> notifications ──> notification_preferences
                    │
                    └── staff acknowledgement/resolution

decision_simulations ──> decision_reviews ──> decision_review_events
```

All 13 Phase 7 tables are staff-only at the database boundary. The backend
service role performs writes; `authenticated` receives `SELECT` only and RLS
requires `public.is_worker_or_admin()`.

## Model governance and reproducibility

- `model_versions` stores a model name (`risk`/`decision`), version, full
  configuration, stable `config_hash`, creator, activation time, and active flag.
- Registration captures the **current runtime configuration**, so the stored
  hash is reproducible from the same environment. A version cannot be silently
  reused with a different configuration.
- Only ADMIN can register or activate. Activation deactivates the previous
  active model and appends a `model_version_events` record with the prior model,
  actor, and reason.
- The active risk configuration is rehydrated by `RiskConfig.from_dict()` and is
  used by risk APIs and decision risk context. If no model is active, runtime
  settings are used.
- Existing `risk_model_runs` retain the model version and configuration hash
  used for every historical calculation; the registry does not rewrite history.

### Evaluation

`POST /api/v1/governance/evaluations` accepts labelled samples with a predicted
score (0–100), binary observed outcome, optional H3 cell, and optional timestamp.

The service calculates threshold metrics (precision, recall, F1, false-positive
rate, specificity, accuracy), ranking metrics (ROC-AUC, PR-AUC), Brier score, and
expected calibration error with calibration bins. It can also produce:

- time-based early/late slices (chronological 70/30 split);
- spatial slices grouped by H3 cell and macro-F1;
- an explicit `INSUFFICIENT_DATA` status when a class is missing.

`SYNTHETIC_FIXTURE` evaluations must be marked synthetic and always carry a
prominent warning. They test the evaluation implementation and are not
real-world model performance. `ground_truth_available` remains false unless a
caller supplies real labelled outcomes and the evaluation is statistically
sufficient. No municipal outcome labels are included in this repository.

## Data ingestion and quality

- `data_sources` records source key, access method, license note, reliability
  (`AUTHORITATIVE`, `VERIFIED`, `COMMUNITY`, `UNVERIFIED`,
  `PLANNING_ASSUMPTION`), adapter, freshness target, retry limit, and required
  fields. No source is seeded as authoritative.
- The adapter interface is `app.ingestion.base.IngestionAdapter`. `manual`
  accepts a staff-authorised batch. `external` exists as an explicit
  unavailable interface; it cannot fabricate a network response.
- `POST /api/v1/operations/sources/{id}/runs` is idempotent by
  `(source_id, idempotency_key)`. A retry with the same key returns the existing
  run. Records are deduplicated by `(source_id, external_id)` within a batch and
  across runs; changed payloads are upserted, unchanged ones counted as
  duplicates.
- Each run records counts, schema fingerprint, provenance, actor, timestamps,
  retry count, and error summary. Invalid or missing-field records are visible;
  the ingestion boundary never silently repairs or infers them.
- `data_quality_snapshots` records `HEALTHY`, `STALE`, `DEGRADED`, or `UNKNOWN`,
  freshness minutes, invalid/duplicate/missing counts, coverage, issues, and
  schema fingerprint.
- Stale/degraded/unknown sources are exposed at `/operations/quality` and
  `/risk/data-quality`. Decision simulations/compares append the same warnings
  to their assumption/warning output.

## Hardening invariants

- `0013_phase7_hardening.py` adds partial unique indexes so at most one model
  version per model name is active and a simulation cannot have two concurrent
  active reviews. Notification and preference RLS is recipient-scoped.
- `0014_model_version_uniqueness.py` removes obsolete config-hash uniqueness so
  distinct version labels with the same runtime configuration remain distinct
  registry entries.
- `0015_ingested_record_provenance.py` persists per-record `observed_at` and
  provenance instead of accepting and discarding them.
- Alert evaluation acquires a PostgreSQL advisory transaction lock per dedupe
  key, and review decisions lock the review row before a state transition.
- A corrupt active model configuration raises an explicit error rather than
  silently substituting runtime defaults.

## Alerts and notifications

- `alert_rules` support `RISK_THRESHOLD`, `DATA_FRESHNESS`,
  `INGESTION_FAILURE`, and `SYSTEM` rule types, configurable operators,
  thresholds, severity, cooldown, and dedupe windows.
- `POST /api/v1/operations/alerts/evaluate` evaluates enabled rules. Alert
  dedupe keys are checked against the larger of cooldown and dedupe window;
  repeated evaluation cannot create an alert storm.
- Alerts have an ACTIVE → ACKNOWLEDGED → RESOLVED lifecycle with actor/time
  fields. Only WORKER/ADMIN can acknowledge or resolve.
- In-app notifications are persisted per staff recipient and checked against
  `notification_preferences` (enabled flag and minimum severity). Delivery uses
  `app.operations.notifications.NotificationAdapter`; external delivery remains
  an unavailable interface and no credentials are accepted.
- Notification access is scoped to the current recipient. Reading another user's
  notification returns 404.

## Human review and approval

- A persisted simulation can be submitted for review with
  `POST /api/v1/decisions/scenarios/{id}/reviews`.
- Review states are `SUBMITTED`, `APPROVED`, `REJECTED`,
  `REVISION_REQUESTED`, with immutable history events.
- Only ADMIN can decide a review, and the submitter cannot approve/reject their
  own review. This is separation-of-duties, not an execution workflow.
- Approval responses always include `execution_authorized=false`,
  `dispatch_performed=false`, and `reservations_created=false`.
- There is no endpoint to execute an approved plan. Any future execution scope
  requires a separate, explicitly authorized design.

## Operational dashboard

`GET /api/v1/operations/dashboard` is a read-only aggregation of real records:

- incident status counts and last-24-hour activity;
- current H3 risk distribution and max score, with availability state;
- registered data sources, freshness, issues, and stale/unknown count;
- active risk/decision models and latest evaluation;
- active alert severity counts and recent alerts;
- scenario/simulation counts and pending reviews;
- database health and environment;
- explicit safety flags.

The `/operations` frontend route renders the same data, with admin-only controls
for registering a source and an alert rule, alert acknowledgement/resolution,
and plan approval/rejection/revision. No demo metrics are generated.

## API summary

| Method | Path | Access |
| --- | --- | --- |
| GET | `/api/v1/governance/models` | WORKER/ADMIN |
| GET | `/api/v1/governance/models/runtime` | WORKER/ADMIN |
| POST | `/api/v1/governance/models` | ADMIN |
| POST | `/api/v1/governance/models/{id}/activate` | ADMIN |
| GET | `/api/v1/governance/models/{id}/events` | WORKER/ADMIN |
| GET | `/api/v1/governance/models/{left}/compare/{right}` | WORKER/ADMIN |
| POST/GET | `/api/v1/governance/evaluations` | WORKER/ADMIN |
| GET | `/api/v1/governance/evaluations/{id}` | WORKER/ADMIN |
| GET/POST | `/api/v1/operations/sources` | staff / ADMIN create |
| GET/POST | `/api/v1/operations/sources/{id}/runs` | WORKER/ADMIN |
| GET | `/api/v1/operations/quality` | WORKER/ADMIN |
| GET/POST | `/api/v1/operations/alerts/rules` | staff / ADMIN create |
| POST | `/api/v1/operations/alerts/evaluate` | WORKER/ADMIN |
| GET | `/api/v1/operations/alerts` | WORKER/ADMIN |
| POST | `/api/v1/operations/alerts/{id}/acknowledge` | WORKER/ADMIN |
| POST | `/api/v1/operations/alerts/{id}/resolve` | WORKER/ADMIN |
| GET | `/api/v1/operations/notifications` | own staff notifications |
| POST | `/api/v1/operations/notifications/{id}/read` | own staff notifications |
| GET/PUT | `/api/v1/operations/notification-preferences` | WORKER/ADMIN |
| GET | `/api/v1/operations/dashboard` | WORKER/ADMIN |
| GET | `/api/v1/risk/data-quality` | WORKER/ADMIN |
| POST | `/api/v1/decisions/scenarios/{id}/reviews` | WORKER/ADMIN |
| GET | `/api/v1/decisions/scenarios/{id}/reviews` | WORKER/ADMIN |
| GET | `/api/v1/decisions/reviews/pending` | WORKER/ADMIN |
| GET | `/api/v1/decisions/reviews/{id}` | WORKER/ADMIN |
| POST | `/api/v1/decisions/reviews/{id}/decision` | ADMIN |

## Security and limitations

- New tables have RLS enabled and are SELECT-only for authenticated database
  roles. API authorization is independent of the frontend.
- Registry activation, source registration, alert-rule creation, and plan
  decisions require ADMIN; monitoring, ingestion, and review submission require
  WORKER/ADMIN.
- Notifications are recipient-scoped. Approval history is append-only by
  application behavior and carries the actor.
- No authoritative municipal outcome dataset, resource feed, or licensed live
  source is included. The ingestion architecture accepts real staff-authorised
  batches but never invents municipal data.
- Evaluation metrics are only as valid as the supplied labels; synthetic
  fixtures are labelled and must not be used as field-performance claims.
- Alert delivery is in-app only. External adapters are not configured.
- Approval is planning governance, not execution authorization.
