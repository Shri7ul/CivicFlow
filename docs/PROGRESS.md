# CivicFlow progress

Last updated: 2026-11-25

## Status

| Phase / goal | Status | Evidence |
| --- | --- | --- |
| Phase 0 — foundation | ACCEPTED | Health, config, errors, CORS, frontend shell, scripts |
| Phase 1 / Goal 03 — database architecture | ACCEPTED | 14 tables, PostGIS types/indexes, Alembic, seed |
| Phase 1 / Goal 04 — authentication/authorization | ACCEPTED | JWKS JWT verification, RBAC, provisioning, audited roles |
| Phase 1.5 — live Supabase integration | ACCEPTED (signup boundary noted) | Live migration, RLS matrix, real ES256 sign-in, browser session |
| Phase 1.6 / Goal 1.6.1 — DB least privilege | ACCEPTED | Migration `0003_acl_hardening`; live ACL counts |
| Phase 1.6 / Goal 1.6.2 — remove legacy HS256 | ACCEPTED | Config, verifier, tests, docs updated; ES256/RS256 only |
| Phase 1.6 / Goal 1.6.3 — real auth acceptance | ACCEPTED (signup boundary noted) | Real users, ES256, provisioning, role change, UI session, cleanup |
| Phase 1.6 / Goal 1.6.4 — docs/report | COMPLETE | README, auth/RLS docs, this progress log |
| Phase 2 / Goal 05 — incident API/lifecycle | ACCEPTED | Migration `0004`, API, live API validation |
| Phase 2 / Goal 06 — incident frontend | ACCEPTED | `/incidents`, `/incidents/new`, `/incidents/[id]`, live browser flow |
| Phase 3 — spatial map, clustering, evidence | ACCEPTED (storage-policy limitation) | Migration `0005`, map/evidence live API + browser runs, 112 backend / 44 frontend tests |
| Phase 4 — incident intelligence | ACCEPTED + COMMITTED | Migration `0006`–`0008`, intelligence/relationship/impact APIs, live API + browser runs, 122 backend / 51 frontend tests |
| Phase 5 — urban risk engine | COMPLETE — committed as `640f173` | Migrations `0009`/`0010`, H3 factor engine + APIs, risk map, live API + browser runs, full verification |
| Phase 6 — decision intelligence | COMPLETE — committed as `a9d6923` | Migration `0011`, scenarios/actions/resources, bounded simulation, strategy comparison, decision workspace, live API + browser runs |
| Phase 7 — operational maturity | COMPLETE — committed as `e4a3ab6` | Migrations `0012`–`0015`, model governance/evaluation, provenance ingestion, freshness monitoring, alerts/notifications, human approvals, operations dashboard, live API + browser runs |
| Phase 8 — real-world validation | COMPLETE — committed as `62c2e02` | Migration `0016`, NYC 311 snapshot + provenance, rolling-origin risk backtest vs 4 baselines, sensitivity, synthetic correlation/planning evidence, validation dashboard/report CLI, live API + browser runs |
| Phase 9 — model diagnosis and external validation | COMPLETE — awaiting review | Migration `0017`, 4 multi-region snapshots, factor audit, 19-variant ablation, robustness suite, bootstrap/sign tests, pre-registered candidate evaluated on 3 holdouts and not activated, research report + `/validation` extension, live API + browser runs |
| Phase 10 — research-to-operations readiness | COMPLETE — committed | Migrations `0018`/`0019`, controlled pilot lifecycle, human review, traceability/export, correlation review with explicit provenance, metadata registry, simulation audit, readiness gate, `/pilot` workspace, live API/browser checks |
| Phase 11 — real ground truth and urban data integration | COMPLETE — ready for review | Migrations `0020`–`0022`, hashed acquisition, 794 real NYC bridge assets, fresh Q3 2026 NYC 311 validation, ground-truth/reference-universe APIs, 16-category readiness, `/pilot` Evidence workspace, live RLS checks |

Phase 3 was committed and pushed as `69cf003`
(`feat(civicflow): complete phase 3 spatial intelligence`). Phase 4 was committed
and pushed as `bfc073e` (`feat(civicflow): implement phase 4 incident
intelligence`). Phase 5 is committed as `640f173`; Phase 6 is committed as
`a9d6923`. Phase 7 is committed as `e4a3ab6`. Phase 8 is committed as `62c2e02`.
Phase 9 is committed for review without rewriting prior history. Phase 10 was
committed as `feat(civicflow): implement phase 10 readiness governance`.
Phase 11 is implemented and verified without activating a model or a pilot.

## Phase 4 implementation checklist

### Repository audit and scope

- [x] Re-read the roadmap, progress log, README, models, migrations, and tests.
- [x] Confirmed no intelligence engine, relationship persistence, or duplicate
  review API existed.
- [x] Confirmed infrastructure/dependency tables existed but held only explicitly
  development-only seed rows, not authoritative municipal data.
- [x] Chose an explainable, human-reviewable scope instead of fabricating datasets.

### Correlation and duplicate detection

- [x] Add deterministic spatial, temporal, category, text, and severity signals.
- [x] Add configurable radius, window, text, confidence, candidate, and impact limits.
- [x] Separate duplicate candidates from related candidates.
- [x] Return per-signal weights, contributions, explanations, reasons, and confidence.
- [x] Never auto-merge, delete, or mutate incidents from suggestions.
- [x] Preserve Citizen visibility in candidate retrieval and relationship listing.
- [x] Avoid excessive queries with bounded PostGIS candidate retrieval and limits.

### Persistence and review

- [x] Add `incident_relationships` with canonical ordering, unique pair/type,
  confidence range, self-link CHECK, FKs, indexes, and timestamps.
- [x] Add `0006` migration, RLS, SELECT-only authenticated grant, and trigger.
- [x] Normalize early Phase 4 CHECK names with `0007`/`0008`.
- [x] Add WORKER/ADMIN review endpoint with idempotent upsert by canonical pair/type.
- [x] Persist reviewer, review time, confidence, signals, and note.
- [x] Reject self-links and non-staff review; map concurrent conflicts to 409.

### Infrastructure and impact foundation

- [x] Add authenticated active-infrastructure reference endpoint.
- [x] Use PostGIS spatial predicates and geography distance with WGS84 handling.
- [x] Return nearby asset distance and dependency-link count.
- [x] Traverse dependency edges breadth-first with depth/node bounds and decaying confidence.
- [x] Label root proximity as `GEOSPATIAL_ASSOCIATION` and graph paths as
  `INFERRED_POTENTIAL`; state that neither is observed damage.
- [x] Document seed-data provenance and missing authoritative asset feed.

### Frontend

- [x] Add typed intelligence API client, types, and formatting helpers.
- [x] Add an incident-detail intelligence panel without removing existing UI.
- [x] Show duplicate and related suggestions with confidence, reasons, signals,
  candidate links, and explicit “decision support” framing.
- [x] Add staff-only confirm/dismiss review controls and reviewed-relationship cards.
- [x] Show infrastructure proximity and impact paths with type/confidence/rationale.
- [x] Add loading, error/retry, empty, threshold, and limitation states.
- [x] Add API/helper tests for serialization, formatting, and inference labels.

### Verification and documentation

- [x] Add backend unit/API/constraint/migration tests for intelligence.
- [x] Run full backend and frontend suites, typecheck, lint, and production build.
- [x] Run live API validation with disposable real users, assets, and dependency data.
- [x] Run live headless-Chrome validation of the rendered intelligence panel.
- [x] Clean up all disposable rows, users, assets, edges, and relationships.
- [x] Update README, backend/frontend READMEs, auth/RLS docs, and intelligence docs.

## Phase 7 implementation checklist

### Governance, evaluation, and ingestion

- [x] Add model registry, activation audit, config hashes, and active-model resolution.
- [x] Add persisted labelled evaluation with threshold, ranking, calibration, temporal, and spatial slices.
- [x] Mark synthetic fixtures explicitly; do not represent them as field performance.
- [x] Add source registry, reliability/license/provenance metadata, adapter interfaces, and explicit unavailable external adapters.
- [x] Add idempotent ingestion, duplicate detection, schema fingerprints, invalid/missing-field counts, and quality snapshots.
- [x] Surface stale/degraded/unknown data to risk and decision users.

### Alerts, approvals, and operations

- [x] Add threshold/freshness/ingestion alert rules with cooldown/deduplication.
- [x] Add in-app notifications, recipient scoping, preferences, and acknowledgement/resolution.
- [x] Add human plan submission, ADMIN approval/rejection/revision, separation of duties, and immutable history.
- [x] Keep approvals non-executing and expose false execution flags everywhere.
- [x] Add real-data `/operations` dashboard with incidents, risk, quality, models, evaluation, alerts, planning, approvals, and health.
- [x] Add admin-only source/rule controls and staff alert/approval interactions.
- [x] Add protected route, navigation, and dashboard integration.

### Verification and documentation

- [x] Add migrations `0012`–`0015` with 13 staff-only tables, RLS, grants, constraints, indexes, hardening invariants, and downgrade.
- [x] Add backend evaluation, governance, ingestion, alerting, dashboard, and review tests.
- [x] Add frontend API/routing tests and type/lint/build validation.
- [x] Run live PostgreSQL migration/RLS checks, live API validation, and headless-Chrome validation.
- [x] Document governance, evaluation methodology, ingestion, quality, alerts, approvals, security, and limitations.

## Phase 6 implementation checklist

### Models and safety

- [x] Audit existing scenario, infrastructure, incident, risk, and RBAC models.
- [x] Add `decision_scenarios`, `decision_actions`,
  `action_resource_requirements`, `response_resources`, and
  `decision_simulations` with staff-only RLS and a complete downgrade.
- [x] Make UNKNOWN the safe resource default; require source/as-of provenance
  for known or assumed availability; never seed fabricated inventory.
- [x] Enforce planning-only behavior: no dispatch, reservation, assignment,
  resource decrement, or incident mutation.

### Planning and simulation

- [x] Add response types, priorities, dependencies, durations, earliest starts,
  costs, expected reductions, and target H3/asset context.
- [x] Implement bounded deterministic scheduling for shared/consumable resources,
  dependency cycles, budgets, horizon, and target risk context.
- [x] Return explicit scheduled/blocked/deferred/unscheduled reasons.
- [x] Add four transparent strategies and objective component scoring.
- [x] Enforce a configurable solver time limit and report solver metadata.
- [x] Persist staff simulations with model/config hash, inputs, result, summary,
  solver metadata, and requester.

### APIs and frontend

- [x] Add staff-only `/decisions/config`, `/metadata`, `/resources`, `/scenarios`,
  actions, simulate, compare, history, and detail APIs.
- [x] Add protected `/decisions` and `/decisions/[id]` routes with scenario
  creation, action planning, resource assumptions, target-cell map, simulation
  results, and strategy comparison.
- [x] Add typed API/types/helpers, routing/nav/dashboard/landing integration, and
  frontend tests.

### Verification and documentation

- [x] Run backend unit/API/engine/constraint/migration/config tests.
- [x] Run frontend typecheck, lint, Vitest, and production build.
- [x] Apply `0011` live; verify `alembic current/check`.
- [x] Live API validation with disposable users, scenarios, resources, actions,
  simulations, and cleanup.
- [x] Headless-Chrome validation of dashboard, workspace, target map, simulation,
  comparison, and dashboard link.
- [x] Document safety, resource assumptions, solver limits, APIs, and RLS.

## Phase 5 implementation checklist

### Model and spatial aggregation

- [x] Audit the existing risk models/schema and preserve the Phase 1
  `risk_cells`/`risk_assessments` tables.
- [x] Add `risk_model_runs` and `risk_cell_snapshots` with staff-only RLS,
  version/config hash, window, resolution, scores, factors, and trends.
- [x] Add migration `0009_urban_risk_engine` with indexes, checks, grants, and
  a complete downgrade; add `0010_risk_factor_default` for the JSON-array
  snapshot default.
- [x] Add validated `RISK_*` configuration and a stable configuration hash.
- [x] Implement H3 aggregation with configurable resolution and GeoJSON/WKT
  boundaries.
- [x] Bound incident and cell queries; fail clearly instead of truncating.

### Explainable scoring and temporal analysis

- [x] Implement nine factors: severity, adjusted density, within-cell spatial
  concentration, recency, active share, category, trend, infrastructure
  exposure, and dependency context.
- [x] Apply only WORKER/ADMIN-confirmed duplicates; expose the adjustment.
- [x] Deduplicate globally across both windows and across H3 boundaries so a
  confirmed duplicate cannot be counted twice or inflate a trend.
- [x] Return raw/normalized values, weights, contributions, availability, and
  explanations.
- [x] Report `incident_activity_score` separately from composite risk.
- [x] Compare the immediately previous equal-length window and classify trends.
- [x] Require full previous-window coverage and minimum combined history before
  asserting a trend direction.
- [x] Compute infrastructure exposure from proximity/type/criticality and
  dependency links, with authoritative/development provenance.

### APIs and security

- [x] Add `/risk/config`, `/risk/cells` (JSON/GeoJSON), `/risk/summary`,
  `/risk/cells/{id}`, `/risk/trends`, and `/risk/infrastructure-exposure`.
- [x] Add WORKER/ADMIN `POST /risk/runs` and `GET /risk/runs` persistence.
- [x] Enforce Citizen minimum-cell-count privacy, withhold trend comparisons
  when either window is below the minimum, and authorize incident briefs.
- [x] Return opaque 404s for hidden cells and 403 for non-staff snapshots.
- [x] Validate resolution/window/bbox/limit and document error codes.

### Frontend

- [x] Add typed risk API/types/formatting helpers.
- [x] Add protected `/risk` route and navigation/dashboard links.
- [x] Preserve the Phase 3 incident map and add H3 GeoJSON fill/line/labels.
- [x] Add window/resolution controls, legend, summary cards, and viewport bbox.
- [x] Add top-cell selection, map drilldown, factor bars, trend/confidence,
  infrastructure exposure, authorized briefs, and limitations.
- [x] Add loading/error/empty/suppressed states and a responsive layout.
- [x] Add frontend API/helper/routing tests.

### Verification and documentation

- [x] Run backend unit/API/constraint/migration/config tests.
- [x] Run frontend typecheck, lint, Vitest, and production build.
- [x] Apply `0009`/`0010` live; verify `alembic current/check`.
- [x] Live API validation with isolated users/incidents/assets/edge + cleanup.
- [x] Headless-Chrome risk map/dashboard validation + screenshot.
- [x] Update README, progress, backend/frontend READMEs, env docs, and
  `backend/docs/risk-engine.md`.
- [x] Record honest limitations: inferred exposure, development assets, sparse
  trends, and privacy thresholds.

## Phase 3 implementation checklist

### Repository audit

- [x] Re-read README, progress tracker, architecture, models, migrations, auth.
- [x] Confirmed existing Phase 2 APIs, PostGIS bbox filtering, and evidence table.
- [x] Confirmed no MapLibre dependency and no storage bucket/policies existed.
- [x] Confirmed `python-multipart` and Supabase Storage configuration were absent.

### Spatial map

- [x] Install and integrate MapLibre GL JS with Next.js.
- [x] Add central Dhaka default viewport.
- [x] Create protected `/map` route and navigation entry.
- [x] Render incident GeoJSON source with native MapLibre layers.
- [x] Add severity fill, status stroke, category labels, and legend.
- [x] Add clustering + cluster expansion.
- [x] Add marker selection, selected-marker highlight, and detail preview.
- [x] Add list/map synchronization.
- [x] Add viewport state, debounce, abort/stale-response protection.
- [x] Combine viewport with status/category/severity/department/search filters.
- [x] Add loading, error, retry, empty, and result-limit states.
- [x] Add zoom/reset/location controls, attribution, and responsive layout.
- [x] Add map-based location picker to incident reporting.

### Evidence

- [x] Add `0005` migration for evidence constraints, index, ACL tightening.
- [x] Create private `incident-evidence` Storage bucket via migration.
- [~] Add Storage RLS policy scoped to incident visibility. Migration attempts
  it conditionally; hosted `storage.objects` is owned by
  `supabase_storage_admin`, so the policy is skipped. There is no client write
  policy and direct reads are deny-all; backend signed URLs remain authorized.
- [x] Add backend Storage client with service-role-only upload/sign/delete.
- [x] Add upload endpoint with count, size, MIME/signature, and filename validation.
- [x] Persist evidence metadata and return safe metadata.
- [x] Add signed URL endpoint after backend authorization.
- [x] Add evidence gallery, upload, progress, retry, and safe viewing to detail.
- [x] Verify Citizen/Worker/Admin API authorization and unauthorized denial.

### Security and quality

- [x] Preserve Auth, RBAC, RLS, and ACL hardening.
- [x] Keep service-role key server-only.
- [x] Validate no path traversal or arbitrary MIME acceptance.
- [x] Add backend tests for spatial/evidence/authorization/storage.
- [x] Add frontend helper/API/upload tests.
- [x] Run typecheck, lint, Vitest, build, pytest, Alembic checks.
- [x] Run live storage/map/browser validation and clean up test data.
- [x] Update README, API docs, spatial/evidence docs, env docs, and acceptance report.

## Phase 7 scope implemented

### Model governance and evaluation

- `model_versions` stores model name/version, full config, config hash, active flag, activation time, creator, and lifecycle events.
- Active risk config is rehydrated for the risk API and decision risk context; historical runs retain their original version/hash.
- Evaluation API calculates precision, recall, F1, FPR, specificity, accuracy, ROC-AUC, PR-AUC, Brier, calibration error, temporal slices, and spatial macro-F1.
- Evaluation records persist method, dataset label, sample count, metrics, slices, warnings, and synthetic/ground-truth flags.

### Ingestion, quality, and alerts

- Sources record access method, license, reliability, adapter, freshness target, required fields, and provenance.
- Manual ingestion is idempotent by source/key, deduplicates external IDs across runs, and records schema/count/error metadata.
- Quality snapshots expose healthy/stale/degraded/unknown, freshness, invalid/duplicate/missing counts, issues, and coverage.
- Alert rules support configurable type/operator/threshold/severity/cooldown; alerts dedupe, notify staff in-app, and have acknowledge/resolve lifecycle.
- Notification preferences and recipient-scoped notification access are enforced.

### Review and operations

- Persisted simulations can enter human review; ADMIN decisions are audited and self-approval is blocked.
- Approval never authorizes execution; response flags remain false.
- `/operations` renders real aggregates from incidents, H3 risk, quality, model/evaluation, alerts, planning, approvals, and database health.

## Phase 6 scope implemented

### Decision model

- `decision-v1` (`0.6.0`) separates planning scenarios from the legacy generic
  `scenarios` tables. Scenarios carry hazard, horizon, optional budget,
  resolution, risk window, and staff owner.
- Actions model type, priority, earliest start, duration, target H3/asset,
  department, expected reduction, known/unknown cost, dependencies, assumptions,
  and resource requirements.
- Resources model explicit availability, source, as-of timestamp, allocation
  mode, unit, and department. UNKNOWN is the default; PLANNING_ASSUMPTION is a
  labeled planning status, not verified inventory.

### Simulation and comparison

- The bounded scheduler respects dependencies, horizon, earliest starts, shared
  capacity, consumable capacity, optional budget, and target risk caps. It
  evaluates four heuristic strategies and reports objective components.
- Solver time limits, elapsed time, timeout state, and algorithm are returned;
  no optimality claim is made.
- Every result includes false `execution_authorized`, `dispatch_performed`, and
  `reservations_created` flags. No operational record is mutated.

### Frontend

- `/decisions` creates/selects scenarios and records explicit planning resources.
- `/decisions/[id]` shows target H3 cells on a MapLibre overlay, action planning,
  resource assumptions, simulation metrics/action plan, warnings, limitations,
  and strategy comparison.

## Phase 5 scope implemented

### Risk engine

- `risk-v1` is deterministic and configuration-driven. Weights, H3 resolutions,
  windows, recency half-life, density saturation, privacy/trend minima, and
  category thresholds are validated at startup and exposed at `/risk/config`.
- Default factor weights sum to 1.0: severity 0.24, density 0.13, spatial 0.07,
  recency 0.14, active 0.08, category 0.08, trend 0.06, infrastructure 0.14,
  dependency 0.06.
- Current and previous windows are loaded in one bounded query. Trend is
  `INCREASING`/`DECREASING`/`STABLE`/`INSUFFICIENT_DATA`; sparse cells do not
  get a confident direction.
- H3 cells at resolutions 7–10 (default 8) return GeoJSON polygons, WKT,
  centers, category/confidence, distributions, and factor explanations.
- Staff runs persist a model version, config hash, window/resolution, and
  per-cell snapshots.

### Adversarial review fixes

- Deduplicate confirmed duplicate clusters globally across the current and
  previous windows before H3 assignment; this removes cross-window and
  cross-cell double counting.
- Renormalize reported factor contributions against the same effective weights
  used for scoring, so contributions always explain the returned risk score.
- Require exact factor, severity, and category configuration keys and freeze
  configuration mappings after validation.
- Treat POLYGON asset containment as zero distance; keep PostGIS bbox filtering
  sargable for the incident GIST index.
- Withhold trends unless the previous window is fully covered by history, and
  withhold Citizen trend comparisons when either window is below the privacy
  minimum.
- Validate H3 drilldown IDs and return the opaque `risk_cell_not_found` response.
- Add `0010_risk_factor_default` so the snapshot JSON-array default matches the
  model contract on live and fresh databases.

### Privacy and exposure

- Citizens see only cells meeting the minimum incident count; suppressed counts
  are reported, and hidden cell detail returns an opaque 404.
- Cell detail incident briefs follow normal incident authorization. Aggregate
  cells never expose reporter identities.
- Infrastructure exposure combines nearby active asset type/criticality and
  dependency-link counts. It is labeled geospatial association, not confirmed
  outage or cascade.
- Dataset provenance reports authoritative, development/unknown, and
  asset-limit truncation.

### Frontend

- `/risk` renders an H3 risk overlay on MapLibre while preserving `/map`.
- Window/resolution controls, viewport bbox filtering, legend, summary cards,
  top-cell selection, factor bars, trends, infrastructure context, authorized
  briefs, and limitations are implemented with responsive/empty/error states.

## Phase 4 scope implemented

### Intelligence API

- `GET /api/v1/incidents/{id}/intelligence` returns duplicate and related
  candidates, visible reviewed relationships, nearby infrastructure,
  dependency-aware potential impacts, thresholds, and limitations.
- Confidence combines distance (0.32), time (0.18), text (0.23), category
  (0.13), severity (0.04), and lifecycle status (0.10). Duplicate classification additionally requires
  the duplicate radius/window, compatible category, text threshold, and
  confidence threshold.
- Text matching is normalized token Jaccard plus sequence similarity. It is
  lexical and intentionally explainable, not an NLP/embedding model.
- `GET /api/v1/infrastructure/assets` exposes active assets to authenticated
  users. No external municipal feed is configured; repository seed assets are
  development-only.
- `GET`/`POST /api/v1/incidents/{id}/relationships` lists visible reviewed
  relationships and lets WORKER/ADMIN users confirm or dismiss a suggestion.
  Pairs are canonical/unique; re-review updates the same row.
- Impact depth `0` is a spatial association; graph-derived entries are
  `INFERRED_POTENTIAL`, decay in confidence, and explicitly disclaim observed
  damage/outage/cascade prediction.

### Persistence and security

- `incident_relationships` stores a canonical incident pair, relationship type,
  status, confidence, signals, note, reviewer, and timestamps.
- Self-relationships are rejected in the API and database.
- RLS limits reads to staff or a pair owned by the caller; `authenticated` has
  SELECT only. Relationship writes remain backend-only.
- Citizens cannot infer another Citizen's incident through candidates,
  intelligence, relationships, or opaque 404 behavior.
- Concurrent review conflicts return `409 relationship_conflict`.

### Frontend

- Incident detail includes an intelligence panel with decision-support framing,
  duplicate/related candidate cards, confidence/reasons/signal details,
  staff-reviewed relationship cards, nearby infrastructure, potential impact
  paths, thresholds, and data limitations.
- Staff see confirm/dismiss review controls; Citizens see read-only context.
- Existing report, lifecycle, map, and evidence flows are preserved.

## Phase 2 scope implemented

- `POST /api/v1/incidents` for authenticated reporting with validated WGS84
  coordinates and optional address.
- `GET /api/v1/incidents` with pagination, status/category/severity/department
  filters, text search, and a PostgreSQL/PostGIS bounding box.
- `GET /api/v1/incidents/{id}` with lifecycle history and evidence metadata.
- `PATCH /api/v1/incidents/{id}` with owner/staff edit rules.
- `POST /api/v1/incidents/{id}/status` for `WORKER`/`ADMIN`, enforcing
  `OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED` (plus
  `OPEN → IN_PROGRESS`), department requirements, `resolved_at`, and immutable
  `incident_status_events`.
- `GET /api/v1/departments` for active assignment options.
- Frontend incident queue, report form, detail view, inline editing, staff
  action panel, and history timeline.
- Route protection extended to `/incidents/**`; backend remains the
  authorization boundary.

## Phase 3 scope implemented

### Map and spatial query

- `/map` protected route, client-only MapLibre dynamic import, OSM raster base
  layer, Dhaka default viewport, zoom/reset/geolocation/attribution controls.
- One GeoJSON source and native layers: clusters + counts, severity fill, status
  ring, category abbreviation labels, selected ring. No DOM marker per incident.
- Cluster expansion, marker selection preview, list/map selection sync.
- `GET /api/v1/incidents` viewport query uses all four bbox parameters plus
  status/category/severity/department/search. 300 ms debounce,
  `AbortController`, and request IDs prevent stale results.
- Report form location picker clicks place a marker and set coordinates.

### Evidence

- `POST /api/v1/incidents/{id}/evidence`, `GET .../evidence`, and
  `GET .../evidence/{id}/url`.
- Server-side signature detection for JPEG/PNG/WebP, 1–5 files, 10 MB/file,
  sanitized display names, server-generated object keys, rollback/cleanup.
- Private bucket and backend service-role upload; signed preview URLs expire
  after 300 seconds by default.
- Detail-page gallery with client preflight, multipart progress, retry, signed
  previews, and link refresh.

## Verification commands

```powershell
# Backend
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check

# Frontend
cd ..\frontend
npm run typecheck
npm run lint
npm test
npm run build

# End-to-end local checks
cd ..
.\scripts\verify.ps1
```

Latest recorded results (Phase 10):

- Backend: **214 passed**.
- Alembic: live revision `0019_phase10_correlation`; `alembic check` reports
  **No new upgrade operations detected** (custom PostGIS type warnings only).
- Frontend: typecheck, ESLint, **80 tests** (25 files), and the 18-route
  production build pass.
- `scripts/verify.ps1` passes (Phase 10 final run).

## Historical live validation evidence (Phases 3–7)

- At the Phase 7 checkpoint, live PostgreSQL 17.12 + PostGIS 3.3.7 had all
  migrations applied through `0015_ingested_provenance`.
- 35 application tables, 39 application RLS policies, 9 triggers, 53 foreign
  keys, 13 unique constraints, 5 GIST indexes. RLS is enabled on all 35
  application tables, including all 13 Phase 7 tables. Evidence MIME/size constraints, the evidence composite
  index, normalized Phase 4 relationship CHECKs, and Phase 5 risk-run indexes
  are present.
- Private `incident-evidence` Storage bucket exists with `public=false`,
  10 MB limit, and JPEG/PNG/WebP allowlist.
- ACLs after `0015`: `anon` has no application-table privileges;
  `authenticated` has SELECT on all 35 application tables, INSERT on incidents
  and generic scenarios, column UPDATE only on `profiles.full_name/phone`, and
  no direct INSERT on evidence, relationship, risk, decision, governance,
  ingestion, alert, notification, or review tables.
- Real isolated Auth users completed sign-in with ES256 tokens, backend JWKS
  verification, profile provisioning, `/auth/me`, role changes, and cleanup.
- Real API validation covered report creation, Citizen scoping, Worker/Admin
  visibility, text/bbox filters, edit locking after acknowledgement, department
  assignment, full lifecycle, history, invalid transitions, and 403/404/409
  boundaries.
- Phase 4 live API validation (disposable real users, assets, dependency edge):
  duplicate and related suggestions with explanations, cross-Citizen candidate
  privacy, staff-only review, relationship persistence/uniqueness, citizen
  relationship hiding, opaque 404 intelligence access, PostGIS asset proximity,
  inferred-impact labeling, authenticated asset listing, and cleanup to zero.
- Phase 7 live API validation (disposable admin/worker, model, source, alert,
  review): model registration/activation audit, synthetic evaluation labelling,
  ingestion idempotency/duplicate/missing-field reporting, alert cooldown and
  notification delivery, second-admin plan approval with false execution flags,
  review history, and dashboard database health; cleanup returned to zero.
- Phase 7 live headless-Chrome validation rendered `/operations` with real
  source, alert, governance, risk, approval, and safety state; screenshot
  captured at `C:\Users\USER\AppData\Local\Temp\civicflow-phase7-operations.png`.
- Phase 6 live API validation (disposable users/scenario/resources/actions):
  versioned config, explicit UNKNOWN/PLANNING_ASSUMPTION resources, unknown
  blocking, scheduled planning action, four-strategy comparison, persistence,
  non-decrementing resource quantities, false dispatch/reservation flags,
  Citizen 403, unauthenticated 401, and cleanup to zero.
- Phase 6 live headless-Chrome validation: `/decisions` dashboard, scenario
  workspace, target-cell map, action list, simulation metrics/action plan,
  strategy comparison, and dashboard link. A screenshot was captured.
- Phase 5 live API validation (disposable users/incidents/assets/dependency
  edge): H3 cells and GeoJSON, all factor keys, PostGIS bbox filtering,
  infrastructure/dependency exposure, summary/trends, Citizen privacy and
  authorized briefs, staff run persistence and snapshot counts, non-staff 403,
  unauthenticated 401, and cleanup to zero.
- Phase 5 live headless-Chrome validation:
  protected `/risk` loaded real cells, summary cards and legend rendered, top
  cell selection loaded factor contributions/infrastructure/limitations,
  decision-support copy was present, and the dashboard linked to the risk map.
  A screenshot was captured.
- Phase 4 live headless-Chrome validation:
  signed-in incident detail rendered the intelligence panel, duplicate
  candidate, explanation details, decision-support label, reviewed/empty
  infrastructure/impact states, thresholds, and limitations.
- Phase 3 live API validation (real users, real Storage):
  bbox query, upload, server-side MIME detection, filename sanitization,
  server-generated path, detail/list metadata, signed URL bytes, direct storage
  read denial, cross-Citizen denial, spoofed MIME rejection, empty-file
  rejection, and unauthenticated rejection all passed.
- Phase 3 live headless-Chrome validation:
  sign-in, protected map route, MapLibre canvas, 3 rendered points, marker
  selection preview, list sync, combined filters/empty state/reset, viewport
  empty/reset, native cluster expansion, geolocation marker, signed evidence
  preview, multipart upload with new preview, report-map coordinate picker, and
  mobile layout all passed.
- Transactional real-role RLS validation confirmed that `incident_status_events`
  is visible to the reporter and staff, and hidden from another Citizen.
- All disposable Auth users, profiles, incidents, status events, evidence rows,
  Storage objects, relationships, infrastructure assets, dependency edges, and
  temporary departments were deleted. Remaining counts were zero.

## Phase 8 implementation checklist

### Dataset and reproducibility

- [x] Audited Phases 1–7 before implementing; did not assume prior reports.
- [x] Selected NYC Open Data / NYC 311 public service requests with a documented
  source URL and portal-terms boundary; no SPDX license was asserted.
- [x] Bounded query: Brooklyn bbox `40.680,-73.990` to `40.710,-73.950`,
  2025-01-01 through 2025-03-31, 12 complaint types.
- [x] Fetched and normalized **5,102** real records; all selected rows had valid
  coordinates and supported types.
- [x] Added schema/period/bbox/coordinate validation, dedup by `unique_key`,
  canonical sorting, canonical SHA-256, and gzip snapshot I/O.
- [x] Snapshot load verifies compressed size, schema version, hash, count, typed
  fields, period, bbox, and duplicate IDs.
- [x] Wrote snapshot through the existing Phase 7 ingestion architecture with
  idempotent run, provenance, observed timestamps, and quality snapshot.
- [x] Registered a `validation_datasets` row with source/run links, hash, path,
  period, region, schema, portal terms, record count, and status.
- [x] Added CLI: `backend/scripts/ingest_nyc311.py`.

### Leakage-safe risk validation

- [x] Added `as_of` to `RiskQuery`; operational behavior is unchanged when unset.
- [x] Ran the actual `RiskEngine` on an isolated in-memory SQLite copy of the
  snapshot; no operational row was read or mutated.
- [x] Rolling-origin temporal holdout with 8 folds, 672h history, 168h target,
  H3-9, top-10.
- [x] Future records never enter features or configuration decisions.
- [x] Added baselines A count, B recent count, C weighted count, D persistence.
- [x] Added precision@k, recall@k, ROC-AUC, and PR-AUC with tie handling.
- [x] Added sensitivity for window 168h vs 336h, H3 resolutions 7/8/9, and risk
  band thresholds.
- [x] Actual empirical result is persisted and explicitly unfavorable:
  CivicFlow PR-AUC `0.884367` vs strongest baseline `0.907690` (lower by
  `0.023323`).

### Synthetic and simulated evidence

- [x] Added 8 hand-labelled synthetic duplicate-correlation cases through the
  real Phase 4 scorer: precision `0.8`, recall `1.0`, F1 `0.888889`.
- [x] Added a bounded synthetic planning scenario through the real Phase 6
  comparison: winner `COST_EFFICIENT`, deterministic repeat, UNKNOWN resource
  blocked from silent availability.
- [x] Labelled evidence as `SYNTHETIC_FIXTURE` or `SIMULATED_PLANNING`, never
  as empirical field ground truth.
- [x] No auto-merge, dispatch, reservation, resource decrement, or incident
  mutation.

### Persistence, reports, API, and UI

- [x] Added migration `0016_validation_workspace` and staff-only
  `validation_datasets` / `validation_experiments` with RLS.
- [x] Experiments are append-only with unique keys; existing results are not
  overwritten.
- [x] Added `/api/v1/validation` overview, datasets, experiments, report, and
  bounded run endpoints. Dataset creation is ADMIN-only.
- [x] Added `/validation` dashboard with real provenance, baseline table,
  sensitivity, findings, limitations, synthetic labels, experiment log, and
  report download.
- [x] Added `backend/scripts/generate_validation_report.py` for JSON/Markdown
  reports from persisted rows.
- [x] Added backend dataset/risk/service/API/migration tests and frontend API
  tests.
- [x] No destructive DB operation, live downgrade, or execution path.

### Verification

- [x] Backend: **176 passed** (Phase 8 final).
- [x] Frontend: **65 tests / 21 files** (Phase 8 final).
- [x] TypeScript typecheck, ESLint, and production build pass.
- [x] `scripts/verify.ps1` passes.
- [x] Live PostgreSQL at `0016_validation_workspace`: 37 application tables,
  41 RLS policies, 58 FKs, 15 unique constraints, 5 GIST indexes.
- [x] Live API/DB/RLS: **51 checks passed**; canonical rows remained 1 dataset /
  3 experiments after cleanup.
- [x] Headless Chrome `/validation`: 14 checks + screenshot.

## Phase 9 implementation checklist

### Diagnostic audit and dataset expansion

- [x] Audited Phase 8 results instead of assuming them; confirmed the frozen
  `phase9-risk-diagnosis-v1` protocol was written before any external data was
  fetched.
- [x] Added three public NYC 311 snapshots with documented query metadata:
  Brooklyn 2025 Q2 (3,715), Manhattan 2025 Q2 (4,670), Staten Island 2025 Q1
  (4,694). The existing Brooklyn 2025 Q1 slice remains the development dataset.
- [x] Every snapshot carries a canonical SHA-256, gzip byte limit, schema
  version, period, bbox, portal terms, and Phase 7 ingestion run link; the CLI
  now supports `--dataset` and `--all`.
- [x] Recorded factor availability, zero share, target association, and pairwise
  redundancy per dataset; unavailable infrastructure/dependency factors are
  explicitly excluded from interpretation.

### Leakage-safe ablation, robustness, and statistics

- [x] Ran 19 fixed ablation variants (full, 9 leave-one-out, 9 single-factor) on
  identical rolling origins with renormalized weights.
- [x] Pre-registered selection: highest mean paired PR-AUC delta on the
  development dataset only; external datasets are never used for selection.
- [x] Robustness suite: H3 7/8/9, windows 72/168/336h, 50%/75% record thinning,
  density strata, threshold bands, and missingness.
- [x] Added percentile bootstrap intervals (2,000 resamples, seed `20261124`)
  and exact two-sided sign tests; the report labels intervals as descriptive
  because rolling origins overlap.
- [x] Added `backend/app/validation/{diagnostics,ablations,robustness,stats}.py`
  and persistence helpers with protocol/variant keys; no activation path exists.

### Honest model decision

- [x] CivicFlow PR-AUC `0.884367` / `0.854554` / `0.869954` / `0.517661` vs best
  baselines `0.907690` / `0.901136` / `0.927668` / `0.541535`: above the
  strongest baseline on **0 of 4** datasets.
- [x] `drop_trend` was selected on development (`+0.006311`, interval includes
  zero) and gained on only 1 of 3 external holdouts with an interval above zero
  (`nyc311-brooklyn-2025q2`, `+0.007970`, `[0.001712, 0.015833]`).
- [x] Decision recorded as mixed evidence: the registered risk-v1 model is
  **retained unchanged** and the candidate is persisted as `NOT_ACTIVATED`.
- [x] No factor weight, threshold, resolution, or model version was changed by
  the protocol; no predictive or causal claim is made.

### Report, API, and dashboard

- [x] Added migration `0017_phase9_diagnostics` (`protocol_key`, `variant_key`,
  protocol index, five research experiment types) without touching prior
  migrations.
- [x] Added `GET /api/v1/validation/research`, `GET .../research/report`, and
  ADMIN-only `POST .../research`; reads are staff-only and bounded to the newest
  200 protocol rows.
- [x] Hardened run inputs: at most 8 dataset keys, each at most 200 characters,
  deduplicated before lookup; unknown keys return `422 dataset_not_found`.
- [x] Added `backend/scripts/run_phase9_research.py` and
  `backend/scripts/generate_phase9_report.py` (strict mode validates all 18
  report sections).
- [x] Extended `/validation` with multi-region results, diagnostics, ablation
  ranking, robustness, statistics, candidate decision, evidence policy, and
  report download. Persisted API data only; empty states stay explicit.
- [x] Added backend stats/analysis/API/dataset/report tests and frontend
  API-client and component tests.

### Verification

- [x] Backend: **204 passed** (Phase 9 final).
- [x] Frontend: **72 tests / 22 files** (Phase 9 final).
- [x] TypeScript typecheck, ESLint, and production build pass.
- [x] `scripts/verify.ps1` passes.
- [x] Live PostgreSQL at `0017_phase9_diagnostics`: both columns and the
  protocol index exist, and the experiment-type constraint accepts the five
  Phase 9 types.
- [x] Live API/DB/RLS: **35 checks passed**, including staff reads, ADMIN-only
  run, Citizen 403, anonymous 401, bounded-input 422s, secret-free report body,
  and cleanup to zero disposable users.
- [x] Headless Chrome `/validation`: Phase 9 cards, executive summary, dataset
  selector, band counts, and report download (`154,222` bytes, 23 keys) verified
  with no console errors.

## Phase 10 implementation checklist

### Audit and scope

- [x] Audited the repository, Phase 7–9 migrations, readiness/research records,
  API, RBAC/RLS, and `/validation` before changing code.
- [x] Confirmed Phase 10 is governance/accountability/readiness, not a
  model-performance or activation phase.
- [x] Preserved Phase 8/9 research data and `/validation`; added the separate
  staff `/pilot` workspace.

### Controlled pilot and human review

- [x] Added 11 additive Phase 10 tables with FKs, unique/check constraints,
  bounded indexes, staff-only RLS, and five append-only event tables.
- [x] Implemented `DRAFT -> PENDING_APPROVAL -> APPROVED -> ACTIVE` plus pause,
  resume, complete, archive, reject, and validated denial paths.
- [x] Enforced ADMIN ownership/reviewers, separation of duties on approval and
  activation, timezone-safe windows, and a readiness gate on activation.
- [x] Added risk-review cases tied to run/cell/pilot, validated status
  transitions, assigned-reviewer or ADMIN decisions, required notes/requested
  evidence, and append-only event history.
- [x] Reviews never modify risk scores, factors, or hazard state; server derives
  reviewer identity and enforces authorization.

### Traceability, correlation, infrastructure, simulation

- [x] Added read-only assessment traceability linking model/config, inputs,
  datasets, factor contributions, spatial cells, time window, reviews, pilot
  context, and explicit missing provenance; JSON export included.
- [x] Added candidate registration, one label per reviewer, majority
  aggregation, precision/agreement, and explicit null recall/F1/TN/FN unless a
  complete attested reference universe exists.
- [x] Fixed the adversarial finding that metrics hardcoded
  `is_simulated: false`: every candidate now requires explicit
  `synthetic_fixture` provenance, migration `0019` persists it, and metrics
  expose `SYNTHETIC`/`OPERATIONAL`/`MIXED`/`UNKNOWN`.
- [x] Added a metadata-only seven-domain infrastructure registry with license,
  coverage, CRS, schema, SHA-256, retrieval, limitations, and validation events;
  no URL fetching, asset ingestion, or availability claim.
- [x] Added read-only simulation audit preserving UNKNOWN resources, false
  dispatch/allocation flags, and `SIMULATED` labels; no execution authorization.

### Readiness, API, and frontend

- [x] Added the Phase 10 15-category scorecard (11 mandatory, 4 advisory; 16
  categories from Phase 11), evidence
  attestations, blockers/owners, and `NOT_READY` / `CONDITIONALLY_READY` /
  `READY_FOR_CONTROLLED_PILOT` aggregation. No PASS or pilot activation is
  hardcoded.
- [x] Added bounded, validated staff/admin endpoints with the shared error
  envelope and server-side role checks.
- [x] Added `/pilot` with readiness, pilots, review queue, correlation,
  traceability, infrastructure, and simulation tabs; loading/empty/error,
  mobile overflow, keyboard-accessible details, and API-derived labels.
- [x] Added frontend types/API/tests without changing `/validation` scope.

### Verification and security

- [x] Backend: **214 passed**; targeted Phase 10 API/migration tests pass.
- [x] Frontend: **80 tests / 25 files**; typecheck, ESLint, and production build
  pass (18 routes).
- [x] Live Supabase at `0019_phase10_correlation`; 11 policies, 5 append-only
  triggers, and the provenance column verified.
- [x] Live API: **20/20 checks** passed before fixture cleanup, including
  spoofed identity rejection, role isolation, null recall/TN, no asset data,
  and no accidental model activation. After `0019`, live migration/drift/state
  checks and automated API tests were re-run.
- [x] Browser workflow on a disposable SQLite database verified pilot approval
  without activation, human review, correlation labelling, infrastructure
  verification, trace export, and truthful readiness denial after cleanup.
- [x] Adversarial checks covered unauthorized activation, privilege escalation,
  impersonation, audit/evidence tampering, false readiness, synthetic-as-real
  claims, fake recall, missing provenance, stale data, wrong transitions, RLS
  bypass, injection, unbounded pagination, and frontend bypass.
- [x] Documented implementation, API, lifecycle, review protocol, scorecard,
  security, adversarial fixes, deployment, limitations, and unresolved gaps.
- [x] No model activation, pilot activation, dispatch, alert, allocation, or
  destructive migration was performed.

### Honest limitations

- Live Phase 10 tables remain empty after fixture cleanup; the browser workflow
  is disposable, synthetic evidence, not production usage.
- Live readiness is `NOT_READY`: freshness failed (511 days), model-versus-
  baseline failed (0/4), human review/correlation/infrastructure/governance/
  operational constraints are blocked, and four advisory categories are
  `NOT_ASSESSED`.
- The live `model_versions` registry and risk runs are empty; Phase 9 persisted
  research does not establish production model readiness.
- Correlation metrics are reviewer sample judgments; recall/F1 remain unknown
  without a complete reference universe, and true negatives are not fabricated.

## Phase 11 implementation checklist

### Acquisition and real data

- [x] Audited Phase 8/9 research provenance, Phase 10 governance, live schema,
  RLS, and APIs before changing behavior.
- [x] Added source-key-only acquisition with exact allowlists, no redirects,
  timeout/retry/byte/record limits, JSON validation and no client URLs.
- [x] Added raw and normalized SHA-256, canonical metadata, schema/spatial
  validation, duplicate/invalid/fallback counts, snapshots, lineage and
  append-only events.
- [x] Made failed acquisition non-destructive and successful acquisition
  idempotent by source and normalized hash.
- [x] Integrated NYC DOT Bridge Ratings `4yue-vjfc`: 794 unique BINs from 3,204
  rows, EPSG:4326, quality `WARN`, independently recomputed hashes.
- [x] Added automated metadata validation for the infrastructure source while
  keeping physical-condition verification explicitly absent.
- [x] Integrated fresh NYC 311 Brooklyn and Manhattan 2026 Q3 slices without
  overwriting historical datasets.

### Evidence, ground truth, correlation and validation

- [x] Added ground-truth assertions with distinct source types, five required
  statuses, creator/reviewer separation, evidence-required verification,
  server identity and append-only events.
- [x] Ensured review cannot alter original assertions or model scores and does
  not serialize actor emails or raw bytes.
- [x] Added immutable correlation reference universes with completeness
  attestation, version/method/snapshot requirements, and null recall/F1/TN/FN
  until prerequisites exist.
- [x] Added Phase 11 external backtests with the registered Phase 9 config
  unchanged; preserved both unfavorable results and `confidence_interval: null`
  with an overlapping-fold explanation.
- [x] Added descriptive 750 m bridge proximity context while keeping
  infrastructure-aware comparison `NOT_ASSESSED`.
- [x] Extended readiness to 16 categories (12 mandatory, 4 advisory); no PASS is
  hardcoded and live state remains `NOT_READY`.

### API, persistence, frontend and security

- [x] Added five additive tables, infrastructure asset provenance/FKs/indexes,
  explicit provenance columns, RLS staff policies and append-only triggers.
- [x] Added strict request schemas that reject identity, status, hash, reviewer
  and provenance spoofing; added bounded pagination.
- [x] Added the `/pilot` Evidence tab with registry, snapshots, ground truth,
  correlation, infrastructure, external results, blockers, loading/error/empty
  and responsive provenance-aware rendering.
- [x] Verified live RLS enabled on all five tables, worker visibility, anonymous
  denial, and append-only update/delete rejection.
- [x] Added backend and frontend tests, preserving all prior tests.

### Verification and honest limitations

- [x] Backend: **232 passed**; frontend: **86 tests / 26 files**; typecheck,
  ESLint and production build passed.
- [x] Live migrations through `0022_snapshot_provenance`; real data acquisition
  and independent recomputation performed.
- [x] No model activation, weight change, pilot approval, dispatch, alert,
  resource allocation or authoritative civic decision occurred.
- [x] No operational ground truth, complete correlation universe or independent
  correlation labels exist; these remain hard blockers.
- [x] Only bridges are integrated (1/7 domains); the other domains are absent.
- [x] CivicFlow beat the strongest baseline on 0/2 fresh slices and 0/6 total;
  no superiority claim is made.

## Known boundaries

- Public self-service `/auth/v1/signup` returned HTTP 429 because the Supabase
  project's email send rate limit was exhausted during earlier validation. The
  confirmation rule was verified with an unconfirmed Admin-created user.
  Confirmation links were not read from an inbox.
- Bounding-box filtering is PostgreSQL/PostGIS-only by design; the SQLite test
  dialect returns `400 spatial_filter_unsupported`.
- The hosted `storage.objects` table is owned by `supabase_storage_admin`. The
  migration role cannot create the intended visibility SELECT policy, so the
  migration skips it with a notice. Direct client Storage access is therefore
  deny-all (verified), which is stricter than scoped reads; signed URL issuance
  remains backend-authorized. See `backend/docs/evidence.md` for the dashboard
  policy SQL and security note.
- Correlation is lexical/heuristic and human-reviewed; there is no NLP or
  embedding model, automatic merge, or automatic incident mutation.
- Infrastructure proximity is a spatial association, and dependency paths are
  inferred graph associations, not observed damage/outage or a calibrated
  cascade prediction.
- Phase 11 integrates real NYC DOT bridge ratings, but the other six
  infrastructure domains still have no authoritative asset feed; remaining
  infrastructure rows are development seed data unless a deployment loads its
  own dataset.
- Risk is decision support, not prediction or confirmed impact. H3 cells are
  analysis units, and sparse or incompletely covered history can suppress trends.
- Minimum-count suppression applies to total cell counts; severity/category
  sub-distributions are not independently suppressed inside an eligible cell.
- Infrastructure exposure/dependencies are geospatial associations, not proven
  outages or cascades. Repository assets are development data unless replaced.
- Phase 6 simulation is a bounded heuristic, not an optimal solver or outcome
  prediction. Expected reductions, durations, and costs are planner inputs.
- Phase 7 evaluation metrics require externally supplied labels; no municipal
  outcome dataset is included. Synthetic fixtures are test-only.
- No authoritative resource inventory, licensed live municipal feed, external
  notification delivery, or plan execution. External adapters remain
  unavailable until a deployment explicitly configures and validates them.
- Department and authoritative infrastructure data must be loaded out of band.
- OSM public raster tiles are used for this phase; production tile usage must be
  reviewed separately.
- Phase 8's target is public 311 complaint activity, not verified hazard impact
  or municipal outcome ground truth. The bounded bbox/period/type selection and
  heuristic category/severity mapping limit external validity.
- The slice is dense (86 H3-9 cells at the first origin); top-k metrics and ROC
  must not be generalized to sparse data or operational decisions.
- CivicFlow underperformed the strongest baseline on the reported Phase 8/9 and
  fresh Phase 11 slices (0/6 total); no superiority claim is made.
- Duplicate-correlation metrics are hand-labelled synthetic fixtures. Planning
  reductions and availability are synthetic assumptions.
- Phase 5 is committed as `640f173`; Phase 6 is committed as `a9d6923`; Phase 7
  is committed as `e4a3ab6`; Phase 8 is committed as `62c2e02`. Phase 9 is
  committed for review without rewriting prior history. Environment files remain
  untracked/ignored.
- Phase 9 adds no new authoritative label source: complaint activity remains a
  proxy, and the external slices test transfer only across three dense NYC
  geographies plus one sparse Staten Island slice.
- Bootstrap intervals describe variability across overlapping origins; they are
  not population confidence intervals and do not make folds independent.

## Suggested next goals

1. Apply the documented `storage.objects` visibility policy through a role that
   owns the hosted table, then verify direct signed-URL-free access.
2. Connect licensed authoritative municipal feeds through the ingestion adapter
   interface and validate source contracts, coverage, and freshness targets.
3. Obtain validated outcome labels and run field-calibrated evaluation before
   making any predictive-performance claim.
4. Add external notification adapters and department/administrative management
   behind the same authorization and audit boundaries.
5. Re-run public signup -> email confirmation -> sign-in after the Supabase
   email rate limit resets.
