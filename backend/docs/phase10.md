# Phase 10 — research-to-operations readiness

This document describes the controlled-pilot, human-review, traceability,
correlation-evaluation, infrastructure-readiness, simulation-audit, and
readiness-scorecard layer added in Phase 10. It is a governance and
accountability phase, not a model-performance change.

Phase 10 does not activate a model, create or change a model-registry row,
dispatch resources, send alerts, allocate capacity, or declare a hazard. Every
readiness result is evidence for a separate human decision. The Phase 9
`drop_trend` evaluation remains `NOT_ACTIVATED`; Phase 10 creates no active
registry entry and treats the absent registry as missing provenance, not as a
successful activation.

## Baseline at the start of Phase 10

| Item | Verified value |
| --- | --- |
| Branch / HEAD | `main` / `a393a7f5545dab9b998a54bf35e35eedba170d05` (`Phase 9`) |
| Remote | `origin/main` at the same commit |
| Worktree | clean before Phase 10 files were added |
| Active model registry | **Empty**: 0 `model_versions` rows. `risk-v1` is code/config with hash `551e455892001c1f58198beac5c7cce3d0659edbbe6c37da36c017ff1061cb5b`, not a live registry row. |
| Candidate | `drop_trend` evaluated in Phase 9 and recorded as `NOT_ACTIVATED`; no candidate registry row exists. |
| Live migration | `0017_phase9_diagnostics` at the start; Phase 10 applied `0018_phase10_pilot_governance` and `0019_phase10_correlation` |
| Persisted research | 4 validated NYC 311 datasets; 44 validation experiments (41 Phase 9 + 3 Phase 8), 43 `COMPLETED` and 1 `FAILED` |

The live database was inspected independently rather than inferred from the
repository: all four snapshots are `VALIDATED`; 41 Phase 9 ablation,
backtest, robustness and diagnostic experiments are persisted (40 completed,
1 failed); 3 Phase 8 experiments are completed. There are **no**
`model_versions`, `risk_model_runs`, `risk_cell_snapshots` or `incidents`
rows. Phase 10 does not create or alter those rows. The absent live model
registry is why no live trace, live model activation, or live human review can
be claimed.

## Objectives and non-goals

Phase 10 exists to answer: **what evidence would an accountable organisation
need before allowing a controlled CivicFlow pilot, and can the system prove
where that evidence came from?**

In scope:

- a controlled pilot record with explicit lifecycle and separation of duties;
- a human review layer over persisted risk assessments;
- an assessment-to-review trace and structured export;
- reviewer-verified duplicate-correlation evaluation with honest metrics;
- metadata-only infrastructure source readiness;
- validation of Phase 8 simulation constraints and UNKNOWN preservation;
- a readiness scorecard with mandatory gates and evidence (15 categories in
  Phase 10; Phase 11 adds mandatory ground truth and extends it to 16).

Out of scope by design:

- model activation or weight/threshold changes;
- automated dispatch, reservation, public alerting, or emergency instructions;
- treating complaints or model scores as confirmed hazards;
- treating synthetic fixtures or candidate suggestions as empirical truth;
- fetching or ingesting infrastructure assets;
- auto-approving a pilot or declaring readiness without evidence.

## Architecture

```text
backend/app/models/pilot.py          SQLAlchemy persistence
backend/app/schemas/pilot.py         Pydantic request contracts
backend/app/governance/pilots.py     lifecycle, separation, audit
backend/app/governance/reviews.py    human review queue and decisions
backend/app/governance/traceability.py assessment trace and provenance
backend/app/governance/correlation.py candidate review and metrics
backend/app/governance/infrastructure.py metadata registry
backend/app/governance/simulation.py  read-only constraint audit
backend/app/governance/readiness.py   readiness scorecard (16 in Phase 11)
backend/app/governance/serialization.py response shaping and disclaimers
backend/app/api/v1/endpoints/phase10.py staff/admin API
backend/alembic/versions/0018_phase10_pilot_governance.py schema
backend/alembic/versions/0019_phase10_correlation.py provenance
frontend/src/components/pilot/       Phase 10 workspace
```

The Phase 10 API is a second router mounted under the existing
`/api/v1/governance` prefix. Staff reads require a worker or administrator
profile. Creation, lifecycle transitions, registry mutations, and manual
readiness evidence require an administrator. Server-side checks are
authoritative; the frontend only hides controls it knows are unavailable.

## Controlled pilot framework

### Lifecycle

```text
DRAFT --SUBMIT--> PENDING_APPROVAL --APPROVE--> APPROVED --ACTIVATE--> ACTIVE
   |                    |                         |                      |
   |                    +--REJECT--> REJECTED     +--REJECT--> REJECTED  +--PAUSE--> PAUSED
   |                                                                          |
   |                                                                       RESUME
   |                                                                          |
   +--------------------------------------------------------------> ARCHIVED  v
                                                          ACTIVE/PAUSED --COMPLETE--> COMPLETED --ARCHIVE--> ARCHIVED
```

`CREATE` is recorded as the initial audit event and does not bypass `DRAFT`.
Every transition is checked against an explicit source-state set. The service
refreshes the pilot with a row lock, validates the action, writes the status
change and an append-only `pilot_transitions` event in one transaction, then
commits.

### Separation of duties

- Only an active administrator can create a pilot.
- The creator and owner cannot approve the same pilot.
- Approval requires at least one assigned reviewer and a complete evaluation
  protocol and criteria.
- The approving administrator cannot activate the pilot.
- Activation and resume require a current readiness report with
  `ready_for_activation = true` and no blockers.
- The evaluation window must still be open.
- Rejection and pause require a reason; every event records the actor id,
  actor email, timestamp, from/to state, and note.

Creating a pilot does not approve it. Approval does not activate it. Activation
does not activate the model and does not dispatch anything.

### Pilot fields

`pilot_key`, name, description, status, mode (`SIMULATION` or `STAGING`), region,
bbox, start/end dates, eligible categories, evaluation protocol, operational
restrictions, data sources, evaluation criteria, owner, creators/approvers/
activators, timestamps, rejection/pause reasons, reviewers, and the exact
readiness report captured at activation.

Because no licensed real pilot is available in this repository, the supported
modes are deliberate staging/simulation modes. A `SIMULATION` pilot is still
only an evaluation plan; it does not become a real operational deployment.

## Human-in-the-loop risk review

Each review case references one persisted `risk_model_runs` row and one
`risk_cell_snapshots` row. Creation validates that the cell belongs to the run,
that the pilot (if supplied) is approved/active/paused, that the assigned
reviewer is active staff, and that the reviewer is assigned to the pilot when
the pilot has reviewers. A unique constraint prevents duplicate cases for the
same run and cell.

### Review states

```text
UNREVIEWED --IN_REVIEW--> IN_REVIEW
UNREVIEWED/IN_REVIEW --ACCEPTED/REJECTED/NEEDS_INVESTIGATION/NEEDS_MORE_DATA--> final state
final state --IN_REVIEW--> IN_REVIEW  (explicit reopen; history preserved)
```

`ACCEPTED` means the reviewer accepts the prediction as a reasonable model
output. It never means the hazard is verified. `NEEDS_MORE_DATA` requires a
non-empty `requested_evidence` field. Every decision requires at least one
character of note and is appended to `risk_review_events` with the reviewer's
server-derived profile id and email. Review decisions never update the risk
score, factor contributions, or any operational record.

The API exposes the queue, case detail, decision endpoint, and separate event
history. Read access is staff-only; assignment and review identity are not
accepted from the client.

## Assessment traceability

`GET /governance/traceability/runs` lists persisted assessments with review
counts. `GET /governance/traceability/runs/{id}` builds a read-only view of:

1. assessment metadata and query parameters;
2. the registered model version and config hash, including whether it matches
   the active configuration and whether it was active at export time;
3. input window, resolution, incident count, and any recorded source dataset
   lineage;
4. spatial units and per-cell scores (bounded `cell_limit`, truncation shown);
5. aggregate factor contribution availability, range, mean, and last
   explanation;
6. human reviews, status counts, reviewers, and pilot context;
7. explicit missing-provenance flags.

The structured export (`GET .../export`) is the same payload returned as a JSON
attachment with `X-Content-Type-Options: nosniff`. It is generated from
persisted rows; no assembly from client input and no mutation. If model
configuration or dataset lineage cannot be linked, `provenance.complete` is
false and the missing items are named rather than reconstructed.

## Reviewer-verified correlation evaluation

Candidate pairs are persisted separately from incident relationships. Each
candidate records its two incident ids, similarity score, method and method
version, universe key, reference-universe metadata, explicit
`synthetic_fixture` provenance, generation timestamp, and creator. The
provenance field is required for new candidates; it is never inferred from the
incident rows. A reviewer can label a pair once as `DUPLICATE`, `NOT_DUPLICATE`, or
`INSUFFICIENT_EVIDENCE` with a required explanation. A unique constraint on
`(candidate_id, reviewer_id)` prevents duplicate labels by the same reviewer.

### Metrics

Labels are aggregated per candidate by majority vote. Ties become
`INSUFFICIENT_EVIDENCE`. Metrics are computed only over candidates that have a
usable label:

- precision = TP / (TP + FP), where positive means the reviewer majority
  labelled the candidate duplicate;
- F1 = harmonic mean of precision and recall;
- recall is computable **only** when the universe declares a complete reference
  set, a positive reference size, the reviewed candidate count equals that
  size, and no candidate abstains. Otherwise recall is `null` and the API gives
  the reason;
- false negatives and true negatives stay `null` unless the complete reference
  universe makes them observable;
- pairwise reviewer agreement is reported only where at least two reviewers
  labelled the same candidate.

These are reviewer sample judgments, not validated municipal ground truth.
Unreviewed candidates are not silently counted as true negatives. Metrics
aggregate the explicit per-candidate provenance into
`synthetic_provenance`: `SYNTHETIC`, `OPERATIONAL`, `MIXED`, or `UNKNOWN`.
`is_simulated` is `true`, `false`, or `null` (unknown/mixed) accordingly; a
synthetic fixture is never reported as operational or empirical evidence. The
API also exposes the universe key, evidence kind, counts, decision distribution,
confusion matrix, agreement, limitations, and explicit
`is_validated_ground_truth: false`.

## Infrastructure data readiness

The registry covers seven domains: roads, bridges, facilities, water, drainage,
emergency services, and transit. It stores metadata only: source key, name,
category, URL, provider, license note, retrieval time, dataset version,
geographic coverage, CRS, schema version, optional SHA-256, update frequency,
known limitations, and a metadata JSON object.

Creating a source writes a `REGISTERED` event and never fetches the URL.
`asset_data` is always `null`. Validation decisions are administrator-only,
require a note of at least ten characters, reject no-op transitions, and record
an append-only event. `VERIFIED` requires a license note, valid 64-hex SHA-256,
coverage, CRS, retrieval time, and schema version. `VERIFIED` means the
metadata passed completeness checks; it does not mean the asset exists, is
complete, current, or licensed for operational use.

Coverage reports one of `VERIFIED_METADATA`, `UNVERIFIED`, or `NO_SOURCE` per
domain and always reports `asset_data_available: false`.

## Decision-simulation validation

The simulation audit is read-only. For each persisted Phase 8 simulation it
checks:

- an objective score and its components are recorded;
- solver, budget, and planning constraints are explicit;
- model version, config hash, and solver algorithm are recorded;
- UNKNOWN resource availability remains UNKNOWN (not converted to available);
- no execution authorization, dispatch, or reservation was recorded;
- an independent `APPROVED` decision review exists;
- risk-context provenance is explicitly available or explicitly absent.

Every result is labelled `SIMULATED`, with `dispatch_permitted: false` and
`resource_allocation_permitted: false`. A passing audit validates recorded
constraints only; it does not validate real-world resource availability and is
not an execution authorization. The overall audit exposes `execution_authorized:
false`.

## Pilot readiness scorecard

Sixteen categories are derived from persisted evidence after the Phase 11
extension. Phase 10 introduced 15 (11 mandatory, 4 advisory); Phase 11 adds the
mandatory ground-truth maturity gate, giving 12 mandatory and 4 advisory.

| Category | Gate | Owner |
| --- | --- | --- |
| Data quality | mandatory | Data engineering |
| Data freshness | mandatory | Data engineering |
| Geographic coverage | mandatory | Data engineering |
| Model versus baseline | mandatory | Model owner |
| Model robustness | mandatory | Model owner |
| Human review coverage | mandatory | Review lead |
| Correlation maturity | mandatory | Review lead |
| Ground truth maturity | mandatory | Review lead |
| Infrastructure availability | mandatory | Infrastructure data owner |
| Auditability | mandatory | Security lead |
| Security | advisory | Security lead |
| Governance | mandatory | Governance lead |
| Operational constraints | mandatory | Operations lead |
| Reviewer training | advisory | Review lead |
| Incident escalation | advisory | Operations lead |
| Deployment and rollback | advisory | Platform lead |

Statuses are `NOT_ASSESSED`, `BLOCKED`, `IN_PROGRESS`, `PASS`, `FAIL`, and
`NOT_APPLICABLE`. A category is `PASS` only when its recorded criteria pass; no
category is hardcoded to pass. Manual attestations are limited to security,
reviewer training, incident escalation, and deployment/rollback, require
evidence, and are recorded by an administrator with an append-only event.

Overall status:

- `NOT_READY` if any mandatory category is not PASS/NOT_APPLICABLE;
- `CONDITIONALLY_READY` if all mandatory categories pass but an advisory one
  does not;
- `READY_FOR_CONTROLLED_PILOT` only if all mandatory and advisory categories
  pass (or are not applicable).

`ready_for_activation` additionally requires all pilot-specific checks to pass.
A READY result is a gate result, not an authorization: activation is still a
separate administrator action, and the scorecard never activates a model.

### Current live result

At the final Phase 10 live check the scorecard was `NOT_READY` with
`ready_for_activation: false` and 11 activation blockers:

- `PASS` (4): data quality, geographic coverage, model robustness, and
  auditability;
- `FAIL` (2): data freshness (latest data 511 days old) and model versus
  baseline (0/4 datasets beat the strongest baseline);
- `BLOCKED` (5): human review coverage, correlation maturity, infrastructure
  availability, governance, and operational constraints, each because no
  persisted evidence exists;
- `NOT_ASSESSED` (4 advisory): security, reviewer training, incident
  escalation, and deployment/rollback.

The four validated datasets and 44 experiments are real persisted research,
but the live Phase 10 tables are empty after the verification fixtures were
removed. There is no live pilot, review case, correlation candidate,
infrastructure source, readiness attestation, simulation, or risk run. This is
the honest production state, not a test fixture.

Phase 11 later refreshed data freshness with Q3 2026 datasets and added real
infrastructure plus ground-truth tables. The live score remains `NOT_READY`;
see [phase11.md](phase11.md) for the current counts and blockers rather than
treating this Phase 10 snapshot as current.

## Data model and migration

Migration `0018_phase10_pilot_governance` revises `0017_phase9_diagnostics` and
adds 11 tables. Migration `0019_phase10_correlation` revises `0018` and adds
the nullable `correlation_candidates.synthetic_fixture` provenance column;
legacy rows remain `NULL` (unknown), while the Phase 10 API requires the field
for every new candidate.

```text
pilots                     pilot_reviewers
pilot_transitions          risk_review_cases
risk_review_events         correlation_candidates
correlation_reviews        infrastructure_sources
infrastructure_source_events readiness_evidence
readiness_evidence_events
```

All additions are additive with named constraints and indexes. No existing
column or row is rewritten. Event tables (`pilot_transitions`,
`risk_review_events`, `correlation_reviews`, `infrastructure_source_events`,
`readiness_evidence_events`) are protected by a PostgreSQL trigger that raises
on UPDATE and DELETE. RLS is enabled on every Phase 10 table; anon/authenticated
write grants are revoked and staff read policies use the existing
`public.is_worker_or_admin()` helper. The backend's service connection writes
through the application service; browser clients cannot bypass it.

Downgrade first drops the `0019` column, then drops the triggers, function,
and Phase 10 tables in reverse order. It is destructive by nature but only
touches Phase 10 objects.

## API

All routes are under `/api/v1/governance`. Mistakes return the shared
`{"error": {"code", "message"}}` envelope. List endpoints use bounded
`limit`/`offset`.

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/readiness` | staff | Current scorecard |
| GET/POST | `/readiness/evidence` | staff / admin | Read or attest advisory evidence |
| GET/POST | `/pilots` | staff / admin | List or create pilots |
| GET | `/pilots/{id}` | staff | Pilot detail and history |
| POST | `/pilots/{id}/reviewers` | admin | Assign reviewer |
| POST | `/pilots/{id}/transition` | admin | Validated lifecycle action |
| GET | `/pilots/{id}/history` | staff | Append-only transitions |
| GET | `/pilots/{id}/readiness` | staff | Scorecard with pilot checks |
| GET/POST | `/reviews` | staff | Queue or open case |
| GET | `/reviews/{id}` | staff | Case detail |
| GET | `/reviews/{id}/events` | staff | Review history |
| POST | `/reviews/{id}/decisions` | assigned reviewer/admin | Record decision |
| GET/POST | `/correlation/candidates` | staff / admin | List or create candidates |
| POST | `/correlation/candidates/{id}/reviews` | staff | Independent label |
| GET | `/correlation/metrics?universe_key=` | staff | Labelled metrics |
| GET | `/correlation/summary` | staff | Candidate counts |
| GET/POST | `/infrastructure/sources` | staff / admin | Metadata registry |
| GET | `/infrastructure/sources/{id}` | staff | Source detail |
| POST | `/infrastructure/sources/{id}/validation` | admin | Metadata decision |
| GET | `/infrastructure/coverage` | staff | Domain coverage |
| GET | `/simulation/audit` | staff | Constraint audit |
| GET | `/traceability/runs` | staff | Assessment list |
| GET | `/traceability/runs/{id}` | staff | Read-only trace |
| GET | `/traceability/runs/{id}/export` | staff | JSON attachment |

Validation errors return 422 with field details. Missing/invalid transitions
return 409; separation-of-duties violations return 403; absent resources return
404; unbounded pagination is rejected. Candidate creation requires
`synthetic_fixture`; omitting it is a 422 rather than an implicit "real" label.

## Frontend

The staff workspace is `/pilot`, linked from the site header. It has seven
tabs: readiness, pilots, review queue, correlation, traceability,
infrastructure, and simulation. Every tab reads the API; readiness is never
computed in the browser. The workspace shows loading, empty, and error states,
explicit SIMULATED labels, missing-provenance warnings, and the distinction
between model prediction and human review. Administrators can apply
server-allowed lifecycle actions, record review decisions, label candidates,
validate infrastructure metadata, and export scorecards/traces/metrics.
Non-admin staff see read-only evidence and controls they are permitted to use;
the server remains authoritative.

## Testing

Backend Phase 10 tests cover the pilot lifecycle, creator/approver/activator
separation, readiness gating, review transitions and append-only audit,
correlation partial and complete-reference metrics, infrastructure verification
requirements, manual-evidence scope, traceability/export, simulation audit,
authentication, and bounded pagination. Migration tests assert the new head,
tables, RLS policies, and append-only triggers. Live PostgreSQL checks confirm
the migration, 11 tables, RLS policies, five append-only triggers, and trigger
function.

Frontend tests cover readiness presentation, blockers, explicit unknown values,
empty states, pilot-list normalization, and API path/body construction for
lifecycle, review, correlation, and registry actions. TypeScript, ESLint, and
the production build are part of verification.

Final recorded runs: backend **214 passed**; frontend **80 tests / 25 files**;
TypeScript, ESLint, and the 18-route production build pass. The browser
workflow is separate from the committed test suite (disposable SQLite and
synthetic fixtures).

## Security and governance properties

- Staff reads require a valid Supabase JWT and an active worker/admin profile.
- Admin-only mutations are checked in the dependency layer, not just the UI.
- Reviewer identity and timestamps come from the server session.
- Audit/event rows cannot be updated or deleted through the database trigger.
- Append-only events are written in the same transaction as the state change.
- Review decisions never mutate risk scores or operational records.
- Phase 10 adds no model/pilot activation bypass; the existing Phase 7
  model-activation endpoint remains separate and was not invoked.
- No dispatch, alert, reservation, or allocation path is added.
- Secrets stay in environment variables and are not returned by any endpoint.
- Structured exports set `nosniff` and are JSON, not HTML.

## Adversarial audit

The Phase 10 review was treated as an adversarial governance test, not a
happy-path demo. The following checks were exercised through API tests, the
live API, live SQL, and the disposable browser workflow.

| Threat | Check | Result | Action |
| --- | --- | --- | --- |
| Unauthorized pilot activation | Attempted `ACTIVATE` in the browser without readiness evidence and through the API | Rejected with `409 readiness_not_met`; pilot stayed `APPROVED` | Readiness gate and distinct activator enforced in the service |
| Privilege escalation | WORKER calls to pilot creation, transitions, correlation creation, infrastructure validation, and manual evidence | `403`; ADMIN-only dependencies hold | Server-side dependency authorization, not UI hiding |
| Impersonation | Client supplied `status`, `created_by`, `approved_by`, or `reviewer_id` | `422` from strict schemas; reviewer identity always derived from the session | `extra="forbid"` and server-derived actor fields |
| Audit modification | Update/delete against append-only event rows | Five Phase 10 event tables have `BEFORE UPDATE OR DELETE` triggers; trigger function is present live | Database trigger plus service append-only writes |
| Evidence tampering | Candidate/infrastructure metadata changed without a new event or reviewer note | Validation requires notes/events; no asset bytes are accepted | SHA-256/license/CRS/schema are metadata attestations, not byte verification |
| False readiness | Scorecard inspection with absent evidence | `NOT_READY`, 11 blockers, `ready_for_activation: false`; manual PASS requires ADMIN evidence | Derived aggregation; no hardcoded PASS or auto-authorization |
| Synthetic reported as real | Original metrics exposed `is_simulated: false` regardless of fixture | **Finding fixed**: candidates now require `synthetic_fixture`; metrics return `SYNTHETIC`/`OPERATIONAL`/`MIXED`/`UNKNOWN`, and `is_simulated` is null when unknown | Migration `0019`, schema/API/service/serializer/UI/tests |
| Fake recall / fabricated negatives | Partial and complete reference universes | Recall/F1 null without a complete attested universe; TN/FN null; no synthetic true negatives | Tests assert nulls and the complete-universe branch |
| Missing provenance | Trace/model/candidate/infrastructure payloads | Trace lists missing provenance; new candidates require provenance; infrastructure exposes metadata only | Explicit fields, no inference from incident rows |
| Stale data presented as fresh | Live readiness | Freshness `FAIL` at 511 days | Scorecard derives age from persisted data |
| Wrong lifecycle transition | Submit/approve/activate/pause/resume/complete/archive attempts | Invalid transitions `409`; missing notes/evidence `400`/`422` | Explicit transition table and validation |
| RLS/role bypass | Authenticated staff, worker, citizen, anonymous reads and writes | Live tables have staff-only SELECT policies; writes are backend-only | RLS plus dependency checks; server is authoritative |
| Information leakage | Error bodies, exports, registry, simulation, trace | Shared error envelope; no secrets, asset bytes, or dispatch payloads; JSON exports with `nosniff` | Explicit serializers and safe responses |
| Unsafe upload | Phase 10 accepts no file uploads | No upload path exists | Registry stores metadata/SHA-256 only; no fetch |
| Injection / unbounded input | Strings, identifiers, pagination, universe keys | Pydantic limits/`extra=forbid`, parameterized SQLAlchemy, bounded `limit`/`offset` | Validation and query bounds |
| Frontend bypass | Direct API calls without the UI | Server rejects unauthorized actors; UI state is not an authority | Backend authorization boundary |
| Operational/model/resource bypass | Activation, dispatch, allocation, alert probes | Phase 10 adds no activation/dispatch/allocation path; the separate Phase 7 model-activation probe rejected empty input with `422` and created nothing; simulation flags are false | No execution path added |
| Missing rollback | Downgrade review | `0019` drops one column; `0018` drops Phase 10 objects only; documented as destructive and backed up | Planned rollback, no automatic trigger |

### Additional findings fixed during verification

- The pilot list serializer intentionally omitted `history` and
  `allowed_actions`; the detail view crashed on the missing arrays. The
  workspace now fetches pilot detail, normalizes array fields, and refreshes
  after transitions.
- Traceability showed a stale `UNREVIEWED` status after a review decision
  because the run list was not refreshed when the tab reopened. The tab now
  reloads run summaries on open.
- The site header forced horizontal overflow at mobile width. The nav is now a
  bounded horizontal scroll container; the body width matches the viewport.
- Earlier documentation implied a live active model registry and omitted empty
  live Phase 10 tables. The README and this document now state the actual
  counts (0 model versions, 0 risk runs, 4 datasets, 44 experiments).

### Unresolved or unverified

- Append-only protection is verified at the DDL/function level and by migration
  tests; no live UPDATE/DELETE was executed against a persisted event row.
- `synthetic_fixture` is an explicit ADMIN attestation, not cryptographic
  provenance. A malicious administrator could mislabel a fixture; the field
  prevents accidental ambiguity, not a lying operator.
- No live pilot, review, candidate, infrastructure source, risk run, or
  empirical label exists. The browser workflow ran on disposable SQLite with
  synthetic fixtures and cannot establish field performance.
- No independent security penetration test, load test, or production incident
  drill was performed. RLS was checked through policy DDL and API role tests,
  not an exhaustive direct-database bypass suite.

## Deployment and rollback

1. Back up the database and record the current Alembic revision.
2. Deploy the backend and frontend versions together.
3. Run `alembic upgrade head`; confirm `0019_phase10_correlation`.
4. Verify RLS/trigger counts and staff/admin endpoint authorization.
5. Do not activate a pilot or model unless readiness and a real operational
   authorization independently support it.

Rollback: deploy the prior application version, then `alembic downgrade
0017_phase9_diagnostics` only if the Phase 10 tables can be removed. This is
destructive to Phase 10 data and must be a planned, backed-up operation. There
is no automatic rollback trigger and no hidden activation flag.

## Limitations and blockers

- Phase 10 is not production-validated for a real municipal pilot. No real
  pilot, licensed infrastructure feed, trained reviewer cohort, or validated
  hazard label set is available in this repository.
- The live scorecard is `NOT_READY`. Model performance remains worse than the
  strongest baseline on all four Phase 9 datasets; freshness is stale; human
  review, correlation, infrastructure, governance, and operational-constraint
  evidence are absent.
- The live `model_versions` registry is empty. The Phase 9 `risk-v1` hash is a
  code/config and experiment artifact, not a live active registry row. No live
  risk run or trace therefore exists, and Phase 10 does not create one.
- The end-to-end browser workflow (pilot creation through activation denial,
  human review, correlation labels, infrastructure verification, trace export,
  and readiness refresh) ran on a disposable local SQLite database with
  synthetic fixtures. That proves workflow behavior, not production data,
  empirical correlation performance, or real infrastructure availability.
- Correlation metrics are only as good as reviewer coverage and the declared
  reference universe. Recall is withheld unless the reference set is complete.
- Infrastructure records are metadata-only; no asset availability is proven.
- Simulation validation does not prove real resource availability and is not
  an execution authorization.
- The frontend has no pilot-creation form; administrators create pilots through
  the documented API. This is a workflow limitation, not an authorization
  bypass.
- The repository's development infrastructure seed data remains unverified for
  operational use.

## What is implemented, tested, and verified

| Area | Implemented | Automated tests | Live Supabase | Browser workflow |
| --- | --- | --- | --- | --- |
| Pilot lifecycle and audit | Yes | Yes | Migration/RLS and read-only/denial checks; no live pilot written | Yes, disposable SQLite + synthetic fixture |
| Human review | Yes | Yes | Empty live table; no live review written | Yes, disposable SQLite + synthetic fixture |
| Traceability/export | Yes | Yes | API empty because 0 risk runs | Yes, disposable SQLite + synthetic fixture |
| Correlation review/metrics | Yes | Yes | Empty live table; no labels | Yes, synthetic fixture only; not empirical |
| Infrastructure registry | Yes | Yes | Empty live table | Yes, fixture metadata; no asset data fetched |
| Simulation audit | Yes | Yes | Empty live simulation set | Empty-state and limitations rendered |
| Readiness gates | Yes | Yes | `NOT_READY`, 11 blockers, `ready_for_activation: false` | Yes, refreshed from evidence |
| RLS/append-only triggers | Yes | Migration + live SQL | 11 policies, 5 triggers, function present | Not applicable |
| Deployment migration | Yes | Migration tests | `0018` + `0019_phase10_correlation` applied | Build and UI exercised |

"Live Supabase" means checked against the real project database or API. The
browser workflow used a disposable local SQLite database and synthetic fixtures
so that no production pilot, review, correlation, infrastructure, or readiness
rows were created. No claim is made that a real controlled pilot, real asset
ingestion, or empirical correlation performance has occurred.

## Future work

1. Obtain a licensed, authoritative infrastructure feed and validate its
   schema, coverage, license, and freshness through the registry.
2. Recruit independent reviewers, complete training, and run a time-boxed
   review cohort on persisted assessments.
3. Define a complete correlation reference universe with documented labels
   before reporting recall.
4. Establish a real operational pilot agreement with named owners, escalation
   paths, rollback criteria, and a stop condition.
5. Re-run the readiness scorecard after evidence changes; never copy a prior
   PASS forward.
