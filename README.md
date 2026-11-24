# CivicFlow

**Urban Impact & Response Intelligence**

CivicFlow is a full-stack platform for modeling interconnected civic incidents,
understanding urban risk, and coordinating municipal response. The repository
currently contains **Phase 0** (application foundation), **Phase 1** (database
architecture + authentication/authorization), **Phase 1.6** (security hardening),
**Phase 2** (incident reporting and lifecycle management), **Phase 3**
(spatial map, clustering, and private evidence), **Phase 4** (explainable
incident intelligence), **Phase 5** (H3 urban risk engine), **Phase 6**
(decision intelligence and scenario planning), **Phase 7** (operational
maturity, model governance, evaluation, data quality, alerts, and approvals),
**Phase 8** (reproducible public-data validation, baseline backtesting, and
explicit experiment evidence), **Phase 9** (model diagnosis, factor
ablation, multi-region external validation, and research reporting), and
**Phase 10** (controlled pilot governance, human risk review, assessment
traceability, reviewer-verified correlation evaluation, infrastructure
metadata readiness, simulation constraint auditing, and a gated readiness
scorecard), and **Phase 11** (hashed real-data acquisition, real NYC bridge
infrastructure, human ground-truth review, correlation reference universes,
and fresh external validation with an evidence workspace).

Phase 8 adds a bounded NYC 311 public-data snapshot, provenance-preserving
ingestion, leakage-safe rolling-origin risk backtesting against four baselines,
sensitivity diagnostics, explicitly labelled synthetic correlation/planning
evidence, append-only experiment records, a `/validation` dashboard, and
reproducible reports. The empirical result is reported honestly: CivicFlow did
not outperform the strongest baseline on this slice.

Phase 9 diagnoses that result and tests it further: four public NYC 311
snapshots across Brooklyn, Manhattan, and Staten Island, a pre-registered
leave-one-out/single-factor ablation (19 variants), robustness checks over H3
resolution, target window, record thinning, density strata, thresholds, and
missingness, bootstrap intervals and exact sign tests, and an 18-section
research report. The candidate variant was evaluated on external holdouts and
**not activated**: mixed evidence retained the registered model unchanged. The
dashboard extension reads persisted records only and labels every result as
empirical observational complaint activity, synthetic fixture, or simulated
planning.

Phase 7 adds model governance and labelled evaluation, provenance-aware
ingestion and freshness monitoring, staff threshold alerts with in-app
notifications, and human plan review/approval. Approval never dispatches,
reserves, assigns, or mutates operational records.

Phase 6 adds staff-only decision scenarios, explicit response-resource
assumptions, bounded scheduling, and strategy comparison. Simulations never
dispatch, reserve, assign, or mutate operational records.

Phase 5 adds spatially aggregated, temporally comparable risk cells with
configurable factors, confidence, trends, infrastructure exposure, a risk map,
and staff-persisted snapshots. Observed incident activity is reported separately
from inferred exposure, and every score carries explanations and limitations.
Scenario simulation, notifications, and authoritative municipal dataset
ingestion remain future work. See [docs/PROGRESS.md](docs/PROGRESS.md) for
current status, verification evidence, and known boundaries.

## What is implemented

### Phase 0 — foundation

- Next.js App Router frontend with strict TypeScript, Tailwind CSS, ESLint, and
  Vitest.
- FastAPI backend with Pydantic Settings, centralized logging, consistent error
  envelopes, request logging, and CORS.
- Versioned `/api/v1` API with application and database health checks.
- Windows PowerShell setup, run, and verification scripts.

### Phase 1 / Goal 03 — database architecture

- 14 PostgreSQL tables with UUID primary keys, UTC timestamps, foreign keys,
  check/unique constraints, and indexes:
  `profiles`, `departments`, `incidents`, `incident_evidence`,
  `incident_status_events`, `incident_clusters`, `incident_cluster_members`,
  `infrastructure_assets`, `dependency_edges`, `risk_cells`,
  `risk_assessments`, `scenarios`, `scenario_results`, and
  `role_change_audits`.
- SQLAlchemy 2.x models with portable tests and native PostgreSQL/PostGIS types.
- Alembic is the schema source of truth. The application never creates tables
  with `Base.metadata.create_all()`.
- PostGIS extension creation, GIST spatial indexes, and JSONB on PostgreSQL.
- Deterministic, non-destructive development seed data.
- Supabase-oriented Row Level Security migration and tests.

### Phase 1 / Goal 04 — authentication and authorization

- Supabase Auth for identity.
- Backend JWT verification with signature validation, expiry, issuer, audience,
  and required-claim checks.
- Asymmetric JWKS verification only (RS256/ES256), with key caching and rotation
  support. The legacy HS256 shared-secret path has been removed.
- Reusable dependencies: `get_current_user`, `get_current_profile`,
  `require_role`, `require_active_user`, `require_admin`, `require_worker`.
- Exactly three application roles: `CITIZEN`, `WORKER`, `ADMIN`.
- Idempotent profile provisioning. New profiles are always `CITIZEN`; privileged
  roles cannot be self-assigned from browser metadata.
- ADMIN-only, audited role changes with self-change and last-active-admin
  protection.
- Frontend sign-in, sign-up, session handling, sign-out, auth-aware navigation,
  optimistic proxy protection, and a protected dashboard placeholder.
- Supabase RLS policies and backend tests with mocked JWKS/fixtures. Tests do
  not require a live Supabase project.

### Phase 2 / Goal 05 — incident reporting and lifecycle

- Authenticated incident reporting with validated WGS84 latitude/longitude and
  PostGIS geography storage.
- Visibility-scoped listing: Citizens see only their own reports; Workers and
  Admins see the citywide queue. Detail access follows the same rule.
- Filters for status, category, severity, department, text, pagination, and a
  PostgreSQL/PostGIS bounding box.
- Owner edits while an incident is `OPEN`; staff edits until `CLOSED`.
- Forward-only lifecycle:
  `OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED`, with department
  assignment required before acknowledgement or work begins.
- Immutable `incident_status_events` history with actor, note, and timestamp.
- Active department reference endpoint for assignment UIs.
- Real frontend routes: `/incidents`, `/incidents/new`, and
  `/incidents/[id]`, with report creation, filtering, detail, editing, staff
  actions, and lifecycle history.

### Phase 8 — real-world validation and urban data

- Bounded, reproducible NYC Open Data / NYC 311 snapshot
  (`nyc311-brooklyn-2025q1`): 5,102 records, 2025 Q1, Brooklyn bbox, 12 civic
  complaint types, normalized schema `nyc311-normalized-v1`.
- Deterministic fetch → schema/coordinate/period validation → dedup →
  canonical SHA-256 snapshot → existing provenance-aware ingestion → dataset
  registry. The portal terms are recorded; no SPDX license is asserted.
- Staff-only `validation_datasets` and `validation_experiments` tables with
  append-only run keys, metrics, baselines, findings, limitations, and
  reproducibility metadata.
- Leakage-safe rolling-origin backtest of the actual Phase 5 `RiskEngine` on an
  isolated SQLite copy: 8 folds, 672h history, 168h target, H3-9, top-10. No
  future records enter a feature or configuration decision.
- Four baselines: incident count, recent count, weighted count, and persistence.
  Ranking metrics: precision@k, recall@k, ROC-AUC, PR-AUC.
- Sensitivity diagnostics for 168h vs 336h windows, H3 resolutions 7/8/9, and
  configured risk bands.
- Explicitly labelled synthetic duplicate-correlation cases (precision `0.8`,
  recall `1.0`, F1 `0.888889`) and planning simulations. Synthetic evidence is
  never presented as field ground truth.
- Protected `/validation` dashboard with real persisted dataset provenance,
  baseline table, sensitivity, findings, limitations, experiment log, and JSON
  report download.
- Report CLI: `backend/scripts/generate_validation_report.py`.
- **Actual result:** CivicFlow mean PR-AUC `0.884367` vs strongest baseline
  (`baseline_recent`) `0.907690`; the persisted finding says it did not exceed
  the baseline. See [backend/docs/validation.md](backend/docs/validation.md).

### Phase 9 — model diagnosis and external validation

- Four pinned public NYC 311 snapshots with documented provenance: Brooklyn
  2025 Q1 (development, 5,102 records), Brooklyn 2025 Q2 (3,715), Manhattan 2025
  Q2 (4,670), Staten Island 2025 Q1 (4,694, the only sparse geography).
- Pre-registered protocol `phase9-risk-diagnosis-v1`: no factor weight, threshold,
  resolution, or model version was changed. Candidate selection is restricted to
  the development dataset; external snapshots are labelled holdouts.
- Factor diagnostic audit: availability, zero share, target association, and
  pairwise redundancy for all nine factors. Infrastructure and dependency
  metadata are absent from the isolated validation universe, so their weight is
  renormalized and that limitation is recorded explicitly.
- Ablation study: 19 variants (full, 9 leave-one-out, 9 single-factor) on identical
  folds with renormalized weights. `only_density` is the strongest single-factor
  variant; `drop_trend` was selected on development.
- Robustness suite: H3 resolutions 7/8/9, 72/168/336h target windows, 50%/75%
  record thinning, density strata, threshold bands, and missingness.
- Statistics: percentile bootstrap intervals (2,000 resamples, seed `20261124`)
  and exact two-sided sign tests over folds. Intervals are descriptive because
  rolling origins overlap.
- **Actual result:** CivicFlow PR-AUC `0.884367` / `0.854554` / `0.869954` /
  `0.517661` against best baselines `0.907690` / `0.901136` / `0.927668` /
  `0.541535` — above the strongest baseline on **0 of 4** datasets. The selected
  `drop_trend` candidate gained on 1 of 3 external holdouts with an interval above
  zero, so the registered model is **retained unchanged** (`NOT_ACTIVATED`).
- Migration `0017_phase9_diagnostics` adds `protocol_key`, `variant_key`, and a
  protocol index to the append-only experiment table, plus five research
  experiment types.
- New `/validation` research section: multi-region table, diagnostics, ablation
  ranking, sensitivity, bootstrap intervals, candidate decision, evidence policy,
  limitations, and JSON report download — persisted data only, no fake stats.
- CLIs: `backend/scripts/run_phase9_research.py` and
  `backend/scripts/generate_phase9_report.py`. See
  [backend/docs/phase9.md](backend/docs/phase9.md).

### Phase 10 — research-to-operations readiness

- Controlled pilot records with explicit `DRAFT → PENDING_APPROVAL → APPROVED
  → ACTIVE → PAUSED/COMPLETED` lifecycle, validated transitions, and
  append-only transition audit. Creation is not approval and approval is not
  activation.
- Separation of duties: the creator/owner cannot approve; the approver cannot
  activate; activation and resume require a READY scorecard plus pilot-specific
  checks. No model activation or dispatch path is added.
- Human-in-the-loop review over persisted H3 assessment cells with
  `UNREVIEWED`, `IN_REVIEW`, `ACCEPTED`, `REJECTED`, `NEEDS_INVESTIGATION`, and
  `NEEDS_MORE_DATA` states. Reviewer identity comes from the JWT profile;
  decisions are timestamped, append-only, and never change the risk score.
- Read-only assessment trace linking a run to its model/config, query inputs,
  spatial units, factor contributions, reviews and pilot context. Missing
  provenance is explicit, and a structured JSON export is available.
- Reviewer-verified correlation candidates with majority labels, precision,
  F1, agreement and a confusion matrix. Recall and true/false negatives remain
  unknown unless a complete reference universe exists. Each candidate declares
  explicit `synthetic_fixture` provenance; metrics report `SYNTHETIC`,
  `OPERATIONAL`, `MIXED` or `UNKNOWN`, and synthetic fixtures are never
  treated as ground truth.
- Metadata-only infrastructure registry for roads, bridges, facilities, water,
  drainage, emergency services and transit. No URL is fetched, no asset is
  ingested, `asset_data` is always `null`, and `VERIFIED` means metadata
  completeness only.
- Read-only simulation audit for recorded objectives, solver constraints,
  reproducibility, human approval and preservation of UNKNOWN resources. Every
  result is `SIMULATED`; no dispatch or allocation is authorized.
- Sixteen-category readiness scorecard (12 mandatory gates, 4 advisory) derived
  from persisted evidence. No PASS is hardcoded; manual attestations require
  admin identity and evidence. Live state remains **NOT_READY**: model-versus-
  baseline failed (0/6 datasets), ground truth and correlation are blocked by
  absent evidence, infrastructure covers 1/7 domains, and no controlled pilot
  exists. Phase 11 refreshed freshness to PASS with data through 2026-09-30.
- New staff workspace `/pilot` (readiness, pilots, review queue, correlation,
  traceability, infrastructure, simulation) with loading/empty/error states,
  admin actions, and JSON exports. Migration `0018_phase10_pilot_governance`
  adds 11 tables, staff-only RLS policies, and append-only triggers;
  `0019_phase10_correlation` adds explicit candidate provenance.
- See [backend/docs/phase10.md](backend/docs/phase10.md) for the lifecycle,
  review protocol, metric definitions, scorecard gates, API, verification and
  limitations.

### Phase 11 — real ground truth and urban data integration

- Safe acquisition adapters with source-specific allowlists, no redirects,
  timeouts, retries, byte/record caps, dual SHA-256, schema and spatial
  validation, duplicate/invalid counts, lineage, immutable snapshots and
  explicit failure handling. Failed fetches never replace valid current data.
- One real infrastructure dataset integrated: NYC DOT Bridge Ratings
  (`4yue-vjfc`), 794 unique BINs from 3,204 rows, EPSG:4326, quality `WARN`.
  Raw and normalized hashes were independently recomputed. Source verification
  is metadata-only; physical condition is not field-verified. One of seven
  domains is integrated, so infrastructure-aware model comparison is
  `NOT_ASSESSED`.
- Ground-truth framework distinguishes citizen reports, AI predictions, human
  observations, official records, field observations, independent evidence and
  resolution evidence. Statuses are `UNVERIFIED`, `IN_REVIEW`, `VERIFIED`,
  `REJECTED` and `INSUFFICIENT_EVIDENCE`; review requires independent
  evidence, a different reviewer, server identity and append-only events.
  Verification never changes the original report or a model score.
- Immutable correlation reference universes with completeness attestation,
  version, optional validated reference snapshot and reviewer independence.
  Recall, F1, false
  negatives and true negatives remain null without a complete universe and all
  labels; no synthetic true negatives are fabricated.
- Fresh external validation on NYC 311 Brooklyn and Manhattan 2026 Q3 using the
  unchanged Phase 9 configuration. CivicFlow did not beat the strongest
  baseline on either slice (Brooklyn PR-AUC 0.830275 versus 0.912868; Manhattan
  0.866929 versus 0.936024). The unfavorable results are preserved and no model
  is activated.
- Extended `/pilot` with an Evidence tab showing the dataset registry, snapshot
  hashes/lineage, quality, freshness, ground truth, correlation universes,
  infrastructure coverage, external results and blockers. All counts are
  server-derived; `REAL`, `SYNTHETIC`, `SIMULATED`, `MIXED` and `UNKNOWN`
  remain distinct.
- Migrations `0020_phase11_evidence`, `0021_gt_provenance` and
  `0022_snapshot_provenance` add five tables, RLS staff policies, append-only
  event triggers, infrastructure asset provenance and explicit provenance
  columns. Live readiness is `NOT_READY`: 0 verified operational ground truth,
  0 correlation universes, 1/7 infrastructure domains and 0/2 fresh results
  beating the strongest baseline.
- See [backend/docs/phase11.md](backend/docs/phase11.md) for sources, licensing,
  acquisition controls, review workflow, external methodology, API, RLS,
  verification and limitations.

### Phase 7 — operational maturity and intelligence validation

- Model registry and activation events with full configuration and stable
  config hash; only ADMIN can activate a model. Active risk configuration is
  rehydrated for risk calculations and decision risk context.
- Labelled evaluation framework: threshold/ranking/calibration metrics,
  time-based and spatial slices, persisted evaluation records, and explicit
  `INSUFFICIENT_DATA` status. Synthetic fixtures are always labelled and are not
  real-world performance evidence.
- Source registry with reliability, license/provenance metadata, adapter
  interfaces, idempotent ingestion runs, persistent duplicate detection,
  schema fingerprints, invalid/missing-field counts, and quality snapshots.
- Staff freshness/quality monitoring, stale/degraded/unknown warnings in risk
  and decision surfaces, threshold/freshness/ingestion alerts, deduplication,
  cooldowns, in-app notifications, and per-user preferences.
- Human review workflow for persisted simulations: submission, approval,
  rejection, revision request, second-admin separation of duties, immutable
  event history, and explicit non-execution safety flags.
- Protected `/operations` dashboard with real incident, risk, source, model,
  evaluation, alert, planning, approval, and health data.

### Phase 6 — decision intelligence and scenario planning

- Staff-only `decision_scenarios`, `decision_actions`,
  `action_resource_requirements`, `response_resources`, and
  `decision_simulations` tables, all protected by RLS.
- Explicit resource availability with provenance and `as_of`; `UNKNOWN` is the
  safe default. `PLANNING_ASSUMPTION` is labeled and never represented as
  verified inventory.
- Bounded deterministic scheduler for priority, dependencies, horizon, budgets,
  shared capacity, consumable resources, and target H3 cells. Actions return
  `SCHEDULED`, `BLOCKED`, `DEFERRED`, or `UNSCHEDULED` with reasons.
- Four transparent strategies (`PRIORITY`, `RISK_REDUCTION`,
  `COST_EFFICIENT`, `BALANCED`) and a comparison endpoint with an explicit
  objective and solver time limit.
- Staff APIs under `/api/v1/decisions`; protected `/decisions` and
  `/decisions/[id]` workspace with target-cell map, action planning, resource
  assumptions, simulation results, limitations, and strategy comparison.
- Planning-only safety contract: no dispatch, reservation, assignment, or
  incident mutation. Every result reports explicit false safety flags.

### Phase 5 — urban risk engine

- Versioned `risk-v1` model with deterministic H3 aggregation and validated
  configuration (`RISK_*` settings, stable `config_hash`).
- Nine explainable factors: severity, adjusted density, within-cell spatial
  concentration, recency, active share, category consequence, previous-period
  trend, infrastructure exposure, and dependency context. The API returns raw
  values, normalized values, weights, contributions, availability, and reasons.
- Configurable resolutions (7–10, default 8), windows (default 7 days, maximum
  90 days), risk bands (`MINIMAL`→`CRITICAL`), recency half-life, density
  saturation, and minimum-history rules.
- Bounded PostGIS queries and bbox filtering; the API rejects oversized
  incident/cell results instead of silently truncating.
- `GET /api/v1/risk/cells` (JSON or GeoJSON), `/risk/summary`, `/risk/trends`,
  `/risk/cells/{h3_cell_id}`, `/risk/config`, and
  `/risk/infrastructure-exposure`.
- `POST /api/v1/risk/runs` and `GET /api/v1/risk/runs` let WORKER/ADMIN users
  persist versioned runs and per-cell snapshots for later comparison.
- Citizen responses apply a minimum-cell-count privacy rule and only return
  incident briefs the caller is authorized to see. Trend comparisons are also
  withheld when either window is below the privacy minimum. Aggregate risk is
  not a disclosure of hidden incident details.
- Protected `/risk` MapLibre H3 map with resolution/window controls, legend,
  viewport filtering, top-cell drilldown, factor bars, trend/confidence,
  infrastructure context, and visible limitations.
- Confirmed duplicate clusters are deduplicated globally across the current and
  previous windows, then across H3 boundaries, before cells are scored.
- Risk is decision support, not a prediction or confirmed impact. Dependency
  exposure is geospatial association, not a confirmed outage or cascade.

### Phase 4 — incident intelligence

- `GET /api/v1/incidents/{id}/intelligence` returns duplicate and related
  candidates with per-signal explanations, confirmed/dismissed reviews,
  nearby infrastructure, dependency-aware potential impact paths, thresholds,
  and data limitations.
- Signals combine PostGIS distance, temporal proximity, category compatibility,
  normalized text similarity, and severity similarity with configurable
  thresholds. Suggestions are computed on demand and are never auto-merged.
- `POST /api/v1/incidents/{id}/relationships` lets WORKER/ADMIN users confirm or
  dismiss a relationship. Pairs are canonical and unique; review provenance is
  persisted with actor, timestamp, confidence, signals, and note.
- Citizen visibility is preserved: a Citizen never sees another Citizen's
  incident, relationship, or intelligence candidate.
- `GET /api/v1/infrastructure/assets` exposes the authenticated active asset
  reference set for future operational tooling.
- Infrastructure proximity is a spatial association only. Dependency paths are
  labeled `INFERRED_POTENTIAL`; the API does not claim observed damage, outage,
  or real-world cascade prediction.
- The incident detail page renders suggestions, explainability details,
  staff-reviewed relationships, infrastructure context, impact paths,
  thresholds, and limitations with loading/error/empty states.

### Phase 3 — spatial map, clustering, and evidence

- Protected `/map` route with client-only MapLibre GL JS rendering, a central
  Dhaka viewport, zoom/reset/location controls, and responsive layout.
- Viewport bounding-box queries reuse `GET /api/v1/incidents`; status, severity,
  category, department, and text filters are combined server-side. Requests are
  debounced and aborted with stale-response protection.
- GeoJSON sources and native MapLibre layers: severity fill, status stroke,
  category labels, native clustering with counts/expansion, selected-marker
  highlight, incident preview, and map/list synchronization.
- Report form includes a map-click coordinate picker in addition to manual
  coordinates and browser geolocation.
- Evidence upload validates count, size, MIME signature, and filename; stores
  metadata in `incident_evidence`; uploads bytes to the private
  `incident-evidence` Supabase Storage bucket through the backend service role;
  and returns only short-lived signed URLs after incident authorization.
- Upload UI provides per-file validation, progress, retry, and private previews
  on the incident detail page.

## Architecture

```text
frontend/
  src/app/
    page.tsx                  Public landing page and real backend health
    login/ signup/            Supabase auth pages
    auth/callback/            PKCE callback exchange
    dashboard/                Protected role-aware workspace
    incidents/                Protected report, list, and detail routes
    map/                      Protected MapLibre incident map
    risk/                     Protected H3 risk map
    decisions/                Protected planning dashboard and scenario workspace
    operations/               Protected operational/governance dashboard
    providers.tsx             Auth provider boundary
  src/components/auth/        Provider, guard, form, navigation, shell
  src/components/map/         Map view and report location picker
  src/components/incidents/   Cards, badges, and evidence gallery
  src/components/risk/        H3 risk map, drilldown, and factors
  src/components/decisions/   Scenario dashboard, workspace, target map
  src/lib/api/                Typed API client and auth/profile/risk/decision calls
  src/lib/auth/               Route safety, role labels, cookie helper
  src/lib/supabase/           Browser client and public configuration
  src/proxy.ts                Optimistic dashboard/incident route protection

backend/
  app/
    api/v1/endpoints/         health, auth, admin, incidents, departments
    auth/                     JWT verification and FastAPI dependencies
    core/                     Settings, logging, middleware, error handling
    db/                       Engine/session factory and health check
    models/                   SQLAlchemy model registry (53 application tables)
    schemas/                  Pydantic request/response schemas
    services/profiles.py      Provisioning, profile update, audited roles
    services/incidents.py     Reporting, visibility, lifecycle, serialization
    services/evidence.py      Evidence validation, upload, signed URL flow
    services/storage.py       Server-only Supabase Storage adapter
    services/intelligence.py  Correlation, duplicate, infrastructure, impact
    risk/                     Versioned H3 risk config, scoring, exposure, engine
    decisions/                Decision config, bounded scheduler, service
    governance/               Model registry, activation, active-config resolution
    evaluation/               Transparent classification/calibration metrics
    ingestion/                Adapter interfaces, idempotent ingest, quality
    operations/               Alerts, notifications, reviews, dashboard
    evidence/                 Allowlisted acquisition, snapshots, ground truth
    validation/               Dataset registry, backtests, fresh external holdouts
    api/v1/endpoints/risk.py  Risk cells, summary, trends, runs, config, quality
    api/v1/endpoints/decisions.py  Scenarios, resources, simulate, compare
    api/v1/endpoints/governance.py  Models and evaluations
    api/v1/endpoints/operations.py  Sources, quality, alerts, notifications, dashboard
    api/v1/endpoints/reviews.py     Human plan review and approval
    api/v1/endpoints/phase11.py     Evidence workspace, snapshots, ground truth
    seed.py                   Deterministic development seed
  alembic/
    versions/0001_initial_schema.py
    versions/0002_auth_rls.py
    versions/0003_acl_hardening.py
    versions/0004_incident_lifecycle.py
    versions/0005_map_evidence_storage.py
    versions/0006_incident_intelligence.py
    versions/0007_relationship_checks.py
    versions/0008_confidence_check_name.py
    versions/0009_urban_risk_engine.py
    versions/0010_risk_factor_default.py
    versions/0011_decision_intelligence.py
    versions/0012_operational_maturity.py
    versions/0013_phase7_hardening.py
    versions/0014_model_version_uniqueness.py
    versions/0015_ingested_record_provenance.py
    versions/0016_phase8_validation.py
    versions/0017_phase9_diagnostics.py
    versions/0018_phase10_pilot_governance.py
    versions/0019_phase10_correlation.py
    versions/0020_phase11_evidence.py
    versions/0021_gt_provenance.py
    versions/0022_snapshot_provenance.py
  tests/                      Config, DB, auth, API, migration, seed tests
```

## Requirements

- Node.js 20.9+ (tested with Node 24.18) and npm 10+
- Python 3.11+ (tested with Python 3.13)
- Git
- A Supabase project (PostgreSQL + PostGIS + Auth) for real database/auth
  integration. No local PostgreSQL server is required for the automated tests.

The committed test suite uses isolated SQLite for structural constraints and
offline SQL rendering for PostgreSQL/PostGIS. A live Supabase integration
validation was also performed: migrations are applied through
`0022_snapshot_provenance`, PostGIS 3.3.7 is installed, the RLS/ACL matrix
has been exercised transactionally and with isolated real Auth users, the
Phase 10 and Phase 11 staff RLS policies and append-only triggers were checked
live, and private storage upload/signed-download was verified end to end. See
`backend/docs/auth-and-rls.md` for database setup and policy details,
`backend/docs/incidents.md` for the lifecycle contract,
`backend/docs/spatial.md` for the viewport API,
`backend/docs/evidence.md` for the evidence/storage boundary,
`backend/docs/risk-engine.md` for the Phase 5 model and API contract, and
`backend/docs/decisions.md` for the Phase 6 planning, resource, and safety
contract, and `backend/docs/operations.md` for Phase 7 governance, evaluation,
ingestion, alerts, approvals, and security, and
`backend/docs/validation.md` for Phase 8 dataset selection, leakage controls,
actual metrics, synthetic evidence, reports, and limitations, and
`backend/docs/phase9.md` for the Phase 9 protocol, ablation, robustness,
external holdout results, statistics, and model decision.

## Quick start (Windows PowerShell)

From the repository root:

```powershell
.\scripts\setup.ps1
```

The script installs frontend packages, creates `backend/.venv`, installs the
backend package, and copies `.env.example` files when local env files are
missing. It never overwrites an existing `.env` or `.env.local`.

### Backend environment

Edit `backend/.env`:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
```

Use the **direct** Supabase database connection (port 5432) for Alembic
migrations when possible. The application can use the transaction pooler
(port 6543). Never place the Supabase service-role key in the frontend.

### Frontend environment

Edit `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://PROJECT_REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
```

Only public browser configuration belongs here. Do not add a service-role key.

### Apply migrations and seed

```powershell
cd backend

# Prefer the direct connection for DDL:
$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://postgres:...@db.PROJECT_REF.supabase.co:5432/postgres"
.\.venv\Scripts\python.exe -m alembic upgrade head

# Deterministic, non-destructive development seed:
.\.venv\Scripts\python.exe -m app.seed
```

`0002_auth_rls.py` is Supabase-specific: it expects Supabase's `auth` schema
and `authenticated` role. Run it against Supabase, not a bare PostgreSQL
database.

Render the PostgreSQL DDL without a live database:

```powershell
$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/civicflow"
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

This renders SQL only. The live project was migrated separately; see
"Live integration validation" below.

### Run

```powershell
.\scripts\run-backend.ps1     # http://localhost:8000
.\scripts\run-frontend.ps1    # http://localhost:3000
```

Other ports are supported:

```powershell
.\scripts\run-backend.ps1 -Port 8010
.\scripts\run-frontend.ps1 -Port 3100 -ApiBaseUrl http://localhost:8010
```

Add the frontend origin to `CORS_ORIGINS` in `backend/.env` when changing ports.

## API

### Public

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Application liveness |
| `GET` | `/api/v1/health/database` | Real `SELECT 1`; `503` when unavailable |

### Authenticated (`Authorization: Bearer <Supabase access token>`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/auth/me` | Current active profile |
| `POST` | `/api/v1/auth/provision` | Idempotently create the caller's CITIZEN profile |
| `PATCH` | `/api/v1/auth/me` | Update only `full_name` / `phone` |
| `PATCH` | `/api/v1/admin/profiles/{id}/role` | ADMIN-only audited role change |
| `POST` | `/api/v1/incidents` | Report an incident |
| `GET` | `/api/v1/incidents` | Visibility-scoped list with filters and pagination |
| `GET` | `/api/v1/incidents/{id}` | Incident detail, lifecycle history, and evidence metadata |
| `PATCH` | `/api/v1/incidents/{id}` | Edit incident content (owner/staff rules) |
| `POST` | `/api/v1/incidents/{id}/status` | WORKER/ADMIN lifecycle transition |
| `GET` | `/api/v1/incidents/{id}/evidence` | Evidence metadata for a visible incident |
| `POST` | `/api/v1/incidents/{id}/evidence` | Upload 1–5 private images |
| `GET` | `/api/v1/incidents/{id}/evidence/{evidence_id}/url` | Short-lived signed preview URL |
| `GET` | `/api/v1/incidents/{id}/intelligence` | Explainable duplicate/related, infrastructure, and impact context |
| `GET` | `/api/v1/incidents/{id}/relationships` | Visible persisted relationship reviews |
| `POST` | `/api/v1/incidents/{id}/relationships` | WORKER/ADMIN confirm or dismiss a relationship |
| `GET` | `/api/v1/infrastructure/assets` | Active infrastructure reference set |
| `GET` | `/api/v1/departments` | Active departments for assignment |
| `GET` | `/api/v1/risk/config` | Versioned risk model and factor metadata |
| `GET` | `/api/v1/risk/cells` | Risk cells as JSON or GeoJSON, with bbox/resolution/window filters |
| `GET` | `/api/v1/risk/summary` | Band totals and freshness for the current window |
| `GET` | `/api/v1/risk/cells/{h3_cell_id}` | Staff-only cell factor drilldown |
| `GET` | `/api/v1/risk/trends` | Smoothed trend comparison with privacy withholding |
| `GET` | `/api/v1/risk/infrastructure-exposure` | Potential asset exposure by cell |
| `POST` `GET` | `/api/v1/risk/runs` | WORKER/ADMIN snapshot run creation and history |
| `GET` | `/api/v1/decisions/config` | Decision model version, solver limit, objective |
| `GET` | `/api/v1/decisions/metadata` | Hazard/action/resource labels |
| `GET` `POST` | `/api/v1/decisions/resources` | Staff resource inventory |
| `PATCH` | `/api/v1/decisions/resources/{id}` | Resource availability/provenance update |
| `GET` `POST` | `/api/v1/decisions/scenarios` | Planning scenario list/create |
| `GET` `PATCH` | `/api/v1/decisions/scenarios/{id}` | Scenario detail/update |
| `POST` `PATCH` | `/api/v1/decisions/scenarios/{id}/actions[/{action_id}]` | Add/update response actions |
| `POST` | `/api/v1/decisions/scenarios/{id}/simulate` | Bounded planning simulation, optional persistence |
| `POST` | `/api/v1/decisions/scenarios/{id}/compare` | Four-strategy comparison |
| `GET` | `/api/v1/decisions/scenarios/{id}/simulations[/{simulation_id}]` | Persisted simulation history/detail |
| `POST` `GET` | `/api/v1/decisions/scenarios/{id}/reviews` | Submit/list human plan reviews |
| `GET` | `/api/v1/decisions/reviews/pending` | Pending staff approval queue |
| `GET` | `/api/v1/decisions/reviews/{id}` | Review state and immutable history |
| `POST` | `/api/v1/decisions/reviews/{id}/decision` | ADMIN approve/reject/request revision |
| `GET` | `/api/v1/governance/models` | Registered model versions |
| `GET` | `/api/v1/governance/models/runtime` | Runtime config versus active model |
| `POST` | `/api/v1/governance/models` | ADMIN register current config as a version |
| `POST` | `/api/v1/governance/models/{id}/activate` | ADMIN activate and audit a version |
| `GET` | `/api/v1/governance/models/{id}/events` | Model lifecycle audit events |
| `GET` | `/api/v1/governance/models/{left}/compare/{right}` | Configuration/evaluation version comparison |
| `POST` `GET` | `/api/v1/governance/evaluations` | Persist/list labelled evaluation results |
| `GET` | `/api/v1/governance/readiness` | Derived 16-category pilot readiness scorecard |
| `GET` `POST` | `/api/v1/governance/readiness/evidence` | Read or ADMIN-attest advisory evidence |
| `GET` `POST` | `/api/v1/governance/pilots` | Staff pilot list / ADMIN pilot creation |
| `GET` | `/api/v1/governance/pilots/{id}` | Pilot detail, reviewers, allowed actions, history |
| `POST` | `/api/v1/governance/pilots/{id}/reviewers` | ADMIN assign a pilot reviewer |
| `POST` | `/api/v1/governance/pilots/{id}/transition` | ADMIN validated lifecycle action |
| `GET` | `/api/v1/governance/pilots/{id}/history` | Append-only pilot transition history |
| `GET` | `/api/v1/governance/pilots/{id}/readiness` | Scorecard plus pilot-specific checks |
| `GET` `POST` | `/api/v1/governance/reviews` | Staff review queue / open a review case |
| `GET` | `/api/v1/governance/reviews/{id}` | Review case, assessment and factor evidence |
| `GET` | `/api/v1/governance/reviews/{id}/events` | Timestamped reviewer decision history |
| `POST` | `/api/v1/governance/reviews/{id}/decisions` | Assigned reviewer/ADMIN decision |
| `GET` `POST` | `/api/v1/governance/correlation/candidates` | Staff candidate list / ADMIN creation (explicit `synthetic_fixture`) |
| `POST` | `/api/v1/governance/correlation/candidates/{id}/reviews` | Independent reviewer label |
| `GET` | `/api/v1/governance/correlation/metrics?universe_key=` | Precision/F1/agreement with explicit unknown recall |
| `GET` | `/api/v1/governance/correlation/summary` | Candidate review counts |
| `GET` `POST` | `/api/v1/governance/infrastructure/sources` | Metadata-only registry / ADMIN registration |
| `GET` | `/api/v1/governance/infrastructure/sources/{id}` | Source metadata and validation history |
| `POST` | `/api/v1/governance/infrastructure/sources/{id}/validation` | ADMIN metadata verification decision |
| `GET` | `/api/v1/governance/infrastructure/coverage` | Seven-domain metadata coverage; no asset data |
| `GET` | `/api/v1/governance/simulation/audit` | Read-only simulation constraint audit |
| `GET` | `/api/v1/governance/traceability/runs` | Persisted risk assessment list with review counts |
| `GET` | `/api/v1/governance/traceability/runs/{id}` | Read-only model/input/factor/review trace |
| `GET` | `/api/v1/governance/traceability/runs/{id}/export` | Structured JSON trace attachment |
| `GET` | `/api/v1/governance/evidence/workspace` | Server-derived Phase 11 evidence workspace |
| `GET` | `/api/v1/governance/evidence/snapshots[/{id}]` | Bounded snapshot registry/detail with provenance |
| `POST` | `/api/v1/governance/evidence/acquire` | ADMIN allowlisted infrastructure acquisition |
| `POST` | `/api/v1/governance/evidence/snapshots/{id}/verify` | ADMIN independent hash/count recomputation |
| `GET` `POST` | `/api/v1/governance/evidence/ground-truth` | Staff assertion list / creation |
| `POST` | `/api/v1/governance/evidence/ground-truth/{id}/submit` | Submit an assertion for review |
| `POST` | `/api/v1/governance/evidence/ground-truth/{id}/review` | Human decision with evidence, creator excluded |
| `GET` | `/api/v1/governance/evidence/ground-truth/{id}/events` | Append-only ground-truth history |
| `GET` `POST` | `/api/v1/governance/evidence/correlation/universes` | Staff list / ADMIN immutable universe creation |
| `GET` | `/api/v1/governance/evidence/correlation/universes/{id}` | Universe detail and completeness attestation |
| `GET` `POST` | `/api/v1/operations/sources` | Source registry / ADMIN registration |
| `GET` `POST` | `/api/v1/operations/sources/{id}/runs` | Run history / idempotent manual ingestion |
| `GET` | `/api/v1/operations/quality` | Source freshness and quality |
| `GET` | `/api/v1/risk/data-quality` | Freshness warnings for risk consumers |
| `GET` `POST` | `/api/v1/operations/alerts/rules` | Alert definitions / ADMIN creation |
| `POST` | `/api/v1/operations/alerts/evaluate` | Evaluate enabled rules with cooldown |
| `GET` | `/api/v1/operations/alerts` | Alert history |
| `POST` | `/api/v1/operations/alerts/{id}/acknowledge` | Staff acknowledgement |
| `POST` | `/api/v1/operations/alerts/{id}/resolve` | Staff resolution |
| `GET` | `/api/v1/operations/notifications` | Own in-app notifications |
| `POST` | `/api/v1/operations/notifications/{id}/read` | Mark own notification read |
| `GET` `PUT` | `/api/v1/operations/notification-preferences` | Own delivery preferences |
| `GET` | `/api/v1/operations/dashboard` | Real operational dashboard aggregate |

A valid Supabase token without a profile receives `403 profile_required`; call
provisioning next. Inactive profiles receive `403 account_inactive`. Role and
activation changes are never accepted from the profile self-update endpoint.

### Error envelope

```json
{
  "error": {
    "code": "insufficient_role",
    "message": "You do not have permission to perform this action."
  }
}
```

JWT contents, secrets, credentials, and raw access tokens are never logged.

## Roles and authorization

| Role | Intended Phase 1 capability |
| --- | --- |
| `CITIZEN` | Own profile; own incident reports and evidence |
| `WORKER` | Citywide incident visibility and response workflows |
| `ADMIN` | Role management, audit read, elevated Supabase policies |

Authorization is enforced on the backend. Frontend navigation and the
dashboard guard improve UX but are not security boundaries. RLS adds a second
layer for direct Supabase access. The FastAPI backend connects with its own
database credentials and always applies its own authorization checks.

Role changes are transactional and write a `role_change_audits` row containing
actor, target, old role, new role, reason, and timestamp. Self-role changes are
rejected. The last active administrator cannot be demoted.

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `testing`, `staging`, `production` |
| `DEBUG` | `false` | Must be false in production |
| `API_V1_PREFIX` | `/api/v1` | Versioned API prefix |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |
| `CORS_ORIGINS` | localhost:3000 | Comma-separated or JSON array; no wildcard with credentials |
| `DATABASE_URL` | empty | Required in production; normalized to `postgresql+psycopg://` |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | `5` / `10` | Pool sizing |
| `DATABASE_CONNECT_TIMEOUT_S` | `5` | Connection timeout |
| `DATABASE_SSLMODE` | empty | Production defaults to `require` for PostgreSQL |
| `SUPABASE_URL` | empty | Required in production |
| `SUPABASE_ANON_KEY` | empty | Public key, stored as a secret type server-side |
| `SUPABASE_SERVICE_ROLE_KEY` | empty | Server-only; never used by browser code |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Verified audience |
| `SUPABASE_JWT_ISSUER` | derived | Defaults to `SUPABASE_URL/auth/v1` |
| `SUPABASE_JWKS_URL` | derived | Defaults to `SUPABASE_URL/auth/v1/.well-known/jwks.json` |
| `SUPABASE_JWKS_CACHE_SECONDS` | `3600` | JWKS cache lifespan |
| `SUPABASE_STORAGE_BUCKET` | `incident-evidence` | Private evidence bucket |
| `SUPABASE_STORAGE_SIGNED_URL_SECONDS` | `300` | Signed preview lifespan (60–3600) |
| `EVIDENCE_MAX_FILE_SIZE_BYTES` | `10485760` | Per-file cap (10 MB) |
| `EVIDENCE_MAX_FILES_PER_UPLOAD` | `5` | Per-request file cap |
| `INTELLIGENCE_DUPLICATE_RADIUS_M` | `250` | Duplicate search radius (metres) |
| `INTELLIGENCE_RELATED_RADIUS_M` | `1500` | Related-candidate search radius |
| `INTELLIGENCE_DUPLICATE_WINDOW_HOURS` | `24` | Duplicate time window |
| `INTELLIGENCE_RELATED_WINDOW_HOURS` | `72` | Related-candidate time window |
| `INTELLIGENCE_DUPLICATE_TEXT_THRESHOLD` | `0.30` | Minimum normalized text score |
| `INTELLIGENCE_DUPLICATE_CONFIDENCE_THRESHOLD` | `0.55` | Minimum duplicate confidence |
| `INTELLIGENCE_RELATED_CONFIDENCE_THRESHOLD` | `0.42` | Minimum related confidence |
| `INTELLIGENCE_INFRASTRUCTURE_RADIUS_M` | `1000` | Asset proximity radius |
| `INTELLIGENCE_IMPACT_DEPTH` / `LIMIT` | `2` / `20` | Dependency-path bounds |
| `RISK_MODEL_VERSION` | `risk-v1` | Version tag stored with cells/snapshots |
| `RISK_MIN/DEFAULT/MAX_RESOLUTION` | `7` / `8` / `10` | H3 resolution bounds |
| `RISK_DEFAULT/MAX_WINDOW_HOURS` | `168` / `2160` | Default and maximum lookback |
| `RISK_RECENCY_HALF_LIFE_HOURS` | `72` | Exponential recency decay |
| `RISK_DENSITY_SATURATION` | `20` | Log density saturation |
| `RISK_INFRASTRUCTURE_RADIUS_M` | `750` | Asset proximity radius |
| `RISK_MAX_INCIDENTS` / `CELLS` | `20000` / `500` | Bounded query caps |
| `RISK_PRIVACY_MIN_INCIDENTS` | `3` | Citizen small-cell minimum |
| `RISK_TREND_MIN_INCIDENTS` | `3` | Minimum current+previous history |
| `RISK_WEIGHT_*` | see config | Nine factors summing to 1.0 |
| `RISK_THRESHOLD_LOW/MODERATE/HIGH/CRITICAL` | `20/40/65/85` | Category bands |

Production validation rejects debug mode, empty CORS origins, a missing
database URL, and a missing Supabase URL. Secret settings use `SecretStr` and
are masked in representations.

### Frontend (`frontend/.env.local`)

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI base URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Public Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anon/publishable key |

If Supabase variables are absent, auth pages show a configuration message
instead of crashing. The production build succeeds without live credentials.

## Database and RLS

- `alembic/versions/0001_initial_schema.py` defines the original 13 tables,
  PostGIS extension creation, spatial indexes, JSONB, and timestamp triggers.
- `alembic/versions/0002_auth_rls.py` adds Supabase helper functions, a profile
  privilege-guard trigger, RLS enablement, policies, and explicit grants.
- `alembic/versions/0003_acl_hardening.py` removes Supabase-inherited
  `TRUNCATE`, `REFERENCES`, `TRIGGER`, and `MAINTAIN` privileges from
  `anon`/`authenticated` on application tables, then restores only the
  SELECT/INSERT/column-UPDATE grants required by the API and PostgREST.
- `alembic/versions/0004_incident_lifecycle.py` adds the immutable
  `incident_status_events` table, its indexes, a visibility RLS policy, and
  SELECT-only grants for `authenticated`.
- `alembic/versions/0006_incident_intelligence.py` adds
  `incident_relationships`, its constraints/indexes, RLS, and SELECT-only grants.
  `0007`/`0008` normalize CHECK constraint names created during early Phase 4
  development.
- `alembic/versions/0009_urban_risk_engine.py` adds `risk_model_runs` and
  `risk_cell_snapshots`, staff-only RLS, SELECT-only authenticated grants, and
  run/cell indexes. The existing `risk_cells`/`risk_assessments` tables remain
  available as the generic Phase 1 risk schema; Phase 5 snapshots are separate.
  `0010_risk_factor_default.py` aligns the snapshot factor-contribution default
  with the JSON-array model contract.
- `alembic/versions/0011_decision_intelligence.py` adds the five staff-only
  decision-planning tables, RLS policies, constraints, indexes, and a complete
  downgrade. Generic `scenarios`/`scenario_results` remain unchanged.
- `alembic/versions/0012_operational_maturity.py` adds 13 staff-only model,
  evaluation, source, ingestion, quality, alert, notification, and review
  tables with RLS, SELECT-only authenticated grants, indexes, and a complete
  downgrade. `0013` adds one-active-model and one-active-review partial unique
  indexes and narrows notification/preferences RLS to the recipient. `0014`
  removes the old config-hash uniqueness that made a second model version label
  silently return the first version. `0015` persists per-record `observed_at`
  and provenance.
- `alembic/versions/0005_map_evidence_storage.py` adds evidence MIME/size
  constraints and a composite index, revokes direct authenticated INSERT on
  `incident_evidence`, and creates the private `incident-evidence` Storage
  bucket. The bucket has no client write policy; uploads and signed URL issuance
  are backend-only. The migration attempts to create a visibility-scoped
  `storage.objects` SELECT policy when the migration role owns that hosted table;
  on this Supabase project `storage.objects` is owned by
  `supabase_storage_admin`, so the policy is skipped and direct Storage reads
  remain deny-all. See [backend/docs/evidence.md](backend/docs/evidence.md).
- The seed is deterministic and idempotent. It creates three departments, five
  infrastructure assets, and three dependency edges. It does not create users
  or invent H3 risk cells.
- Seed refuses to run in production.

See [backend/docs/auth-and-rls.md](backend/docs/auth-and-rls.md) for policy
details, Supabase setup, and security caveats.

## Live integration validation

The configured Supabase project was validated on **2026-11-23** and rechecked on **2026-11-24**:

- Database and Auth project references match between backend and frontend.
- Auth health endpoint returned `200`; JWKS returned a valid ES256 signing key.
- PostgreSQL 17.12 was reachable over TLS through the configured pooler.
- PostGIS 3.3.7 is installed in the `public` schema.
- Alembic is at `0022_snapshot_provenance`; 53 application tables, 57
  application RLS policies, 102 foreign keys, 29 unique constraints, and 6 GIST
  indexes exist (plus `alembic_version` and PostGIS
  `spatial_ref_sys`). The private `incident-evidence` bucket exists with
  a 10 MB limit and JPEG/PNG/WebP allowlist.
- RLS was exercised with synthetic JWT claims inside a rolled-back transaction
  for anonymous, Citizen, Worker, and Admin behavior. No validation rows were
  persisted. `storage.objects` has no policy for this bucket; direct
  authenticated Storage reads are denied (verified `404`), while backend-issued
  signed URLs work.
- Live least-privilege hardening removed inherited `TRUNCATE`, `REFERENCES`,
  `TRIGGER`, and `MAINTAIN` grants from `anon`/`authenticated`; `service_role`
  was intentionally left unchanged. Anonymous now has no application-table
  grants. After `0022`, authenticated has SELECT on the application tables,
  INSERT on incidents and generic scenarios, column UPDATE on
  `profiles.full_name/phone` only, and no direct INSERT on `incident_evidence`,
  `incident_relationships`, `risk_model_runs`, `risk_cell_snapshots`, or the
  Phase 6/7 staff-only tables; those tables are SELECT-only for authenticated
  and never writable through the API role.
- Phase 7 live validation created isolated Auth users, a registered/activated
  model version, a synthetic evaluation, an UNVERIFIED manual source with
  idempotent ingestion, a threshold alert, in-app notification, and a
  two-administrator plan review. It verified activation audit events, duplicate
  and missing-field reporting, alert deduplication, non-execution approval
  flags, review history, and dashboard health; all rows/users were deleted.
- Phase 8 live validation ingested the 5,102-record NYC 311 snapshot through the
  existing provenance-aware source pipeline, verified a validated dataset with
  snapshot hash and portal terms, and exercised 51 API/DB/RLS checks. It
  confirmed staff RBAC, ADMIN-only registration, append-only experiments,
  empirical-vs-synthetic-vs-planning labels, the full baseline table, explicit
  unfavorable findings, report hashes, non-execution flags, and Citizen RLS
  denial. A metadata-only dataset could not fabricate records. Headless Chrome
  rendered `/validation` with real provenance, sensitivity, limitation, and
  synthetic-evidence sections and captured a screenshot.
- Phase 9 live validation (2026-11-24) confirmed migration
  `0017_phase9_diagnostics`, the `protocol_key`/`variant_key` columns, the
  protocol index, and all five research experiment types, then exercised 35
  API/DB/RLS checks: staff-only research reads, ADMIN-only runs, Citizen `403`,
  anonymous `401`, bounded-input `422`s (unknown, oversized, and too many
  dataset keys), secret-free report bodies, and cleanup to zero disposable
  users. Headless Chrome `/validation` rendered the Phase 9 cards, executive
  summary, multi-region table, dataset selector, band counts, and report
  download (154,222 bytes, 23 top-level keys) with no console errors.
- Phase 9 persisted results are deliberately unfavorable: CivicFlow was above
  the strongest baseline on **0 of 4** datasets, and the pre-registered
  `drop_trend` candidate is recorded as `NOT_ACTIVATED` because external
  holdout evidence was mixed. No model configuration changed.
- Phase 10 live validation (2026-11-24) applied migrations
  `0018_phase10_pilot_governance` and `0019_phase10_correlation`, exercised
  staff-only pilot/review/correlation/infrastructure/traceability APIs, checked
  the then-15-category scorecard (16 from Phase 11) and `NOT_READY` state, and verified the new RLS
  policies and append-only triggers inside rolled-back transactions. No pilot
  was approved or activated and no model-registry row was created.
- Phase 11 live validation (2026-11-24) applied `0020_phase11_evidence`,
  `0021_gt_provenance` and `0022_snapshot_provenance`; acquired and
  independently recomputed one real infrastructure snapshot (794 NYC bridge
  assets) and two fresh Q3 2026 NYC 311 datasets; exercised the evidence
  workspace and ground-truth API; and confirmed worker visibility, anonymous
  denial and append-only rejection for the five new tables. Both fresh
  backtests failed to beat the strongest baseline and are preserved as such.
  No model, pilot, dispatch, alert or resource allocation was activated.
- Phase 7 live headless-Chrome validation rendered `/operations` with a real
  source, alert, governance, risk, approval, and safety state, and captured a
  screenshot.
- Phase 6 live validation created isolated Auth users, a decision scenario,
  explicit planning/unknown resources, actions, simulations, and a comparison.
  It verified staff-only access, unknown-resource blocking, planning-assumption
  labelling, persistence, resource non-decrement, safety flags, Citizen 403,
  unauthenticated 401, and cleanup to zero. Headless Chrome verified `/decisions`,
  the scenario workspace, target-cell map, simulation result, strategy
  comparison, and dashboard link.
- Phase 5 live validation created isolated Auth users, incidents, infrastructure
  assets, and a dependency edge. It verified H3/GeoJSON cells, factor
  explanations, bbox filtering, Citizen minimum-count suppression, authorized
  incident briefs, staff snapshot persistence, run history, and cleanup to zero.
  Headless Chrome verified `/risk`, the H3 overlay, top-cell drilldown, factor
  explanations, infrastructure/limitations copy, and the dashboard link.
- Real Supabase Auth users were created only for isolated validation and deleted
  afterward. Sign-in issued real ES256 access tokens; the backend accepted them
  through the live JWKS, profile provisioning worked, `/auth/me` returned the
  expected roles, and a real role change created an audit row.
- Public `/auth/v1/signup` returned `429` because the project's email rate limit
  was exhausted by validation attempts. The confirmation rule was still verified
  with an isolated unconfirmed user (`email_not_confirmed` before admin
  confirmation, successful sign-in after). Test identities were created through
  the Supabase Admin API with confirmation enabled, then deleted.
- Headless Chrome completed a real UI login as a Citizen, rendered the
  dashboard, restored the session after reload, logged out to `/`, and confirmed
  that `/dashboard` redirected to `/login` afterward. The profile was
  auto-provisioned by the frontend.
- Phase 2 live validation used isolated real Auth users. A Citizen created and
  edited a report; a Worker saw the citywide queue, assigned a temporary
  department, and advanced the incident through `ACKNOWLEDGED`, `IN_PROGRESS`,
  `RESOLVED`, and `CLOSED` in headless Chrome. The Citizen then saw the closed
  incident and no edit action. PostgreSQL/PostGIS bounding-box filtering,
  PostGIS WKT round-tripping, and lifecycle history were verified live.
- A transactional real-role RLS check confirmed that lifecycle history is
  visible only to the incident reporter and staff.
- Phase 4 live validation created isolated real users, incidents, assets, and a
  dependency edge. It verified duplicate suggestions, cross-Citizen privacy,
  staff-only relationship review, relationship persistence/uniqueness, opaque
  404s, PostGIS asset proximity, inferred-impact labeling, authenticated asset
  listing, and cleanup back to zero. Headless Chrome verified the rendered
  intelligence panel, duplicate explanation, empty states, thresholds, and
  limitations.
- Phase 3 live validation exercised real Supabase Auth, PostGIS bbox filters,
  private Storage upload, MIME/filename/size validation, signed URL download,
  and denial of another Citizen's evidence. Headless Chrome verified map render,
  marker selection, list sync, combined filters, viewport reset, cluster
  expansion, geolocation, report map picker, signed image preview, upload
  progress, mobile layout, and route protection.
- All test users, profiles, incidents, evidence rows, Storage objects, lifecycle
  events, relationships, infrastructure assets, dependency edges, and temporary
  departments were deleted; Auth/application counts returned to zero.

## Testing

### Full verification

```powershell
.\scripts\verify.ps1
```

### Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Coverage includes configuration validation, health/error/routing behavior,
model and constraint tests, SQLite migration upgrade/downgrade, offline
PostgreSQL DDL rendering, seed idempotency, JWT verification (ES256/RS256
JWKS rotation and HS256 rejection), provisioning, RBAC matrix, audited role changes,
last-admin protection, incident visibility, validation, editing rules,
lifecycle transitions, history, department assignment, duplicate/related
scoring, relationship review and privacy, infrastructure proximity, and
dependency-path labeling, H3 boundaries, spatial concentration, trend
classification, risk privacy, GeoJSON rendering, and risk run/snapshot
persistence.

### Frontend

```powershell
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

Vitest covers the API client, auth/profile API calls, incident query
serialization and lifecycle helpers, open-redirect protection, optimistic
cookie handling, auth state derivation, role labels, public Supabase
configuration, intelligence API calls, confidence/distance formatting, and
suggestion-vs-inference labels, risk formatting, and risk API serialization.

### Verification boundary

- **Executed:** SQLite structural tests, PostgreSQL offline SQL rendering,
  live PostgreSQL migration/upgrade, PostGIS 3.3.7 verification, live
  `alembic check`, live RLS policy matrix inside a transaction, live backend
  health/database/JWT rejection paths, and headless-browser login/signup-page
  rendering with a failed live sign-in.
- **Executed with real Auth users:** Admin-created confirmed identities,
  password sign-in, ES256 access tokens, backend JWKS validation, profile
  provisioning, idempotency, `/auth/me`, Citizen/Worker/Admin enforcement,
  audited role change, headless browser session restoration, logout,
  protected-route redirection, incident report/edit/list/detail, department
  assignment, and the full incident lifecycle.
- **Boundary:** public self-service signup could not complete because the
  project returned HTTP 429 for the email send rate limit. Confirmation
  enforcement was validated separately. Email confirmation links were not
  followed in an inbox.
- Live RLS also used synthetic JWT claims and rolled-back rows for policy-matrix
  testing; no synthetic rows were persisted.

## Security notes

- `.env` files and local secrets are ignored by Git.
- The frontend receives only public Supabase configuration.
- The backend verifies JWTs; it never trusts a decoded payload without a valid
  signature.
- Tokens and credentials are not logged.
- Role changes are ADMIN-only, transactional, and audited.
- Production CORS requires explicit origins; wildcard plus credentials is
  rejected.
- RLS is a defense-in-depth layer for Supabase clients, not a replacement for
  backend authorization.

## Current status

| Area | Status |
| --- | --- |
| Phase 0 foundation | Complete |
| Database models and Alembic migrations | Complete |
| PostGIS schema and spatial indexes | Applied live; PostGIS 3.3.7 verified |
| Seed data | Complete and tested |
| Supabase JWT verification | Complete and tested with fixtures |
| Role-based authorization | Complete and tested |
| Profile provisioning / audited roles | Complete and tested |
| Frontend auth foundation | Complete and tested |
| Supabase RLS | Applied live; synthetic-claim policy matrix and real-user flows verified |
| ACL least privilege | Applied live through `0016_validation_workspace`; verified directly |
| Legacy HS256 JWT path | Removed; ES256/JWKS only |
| Incident report/list/detail/edit | Complete and tested |
| Incident lifecycle and history | Complete and tested |
| Incident frontend workspace | Complete and tested |
| PostGIS bounding-box filter | Live-verified on PostgreSQL; explicit 400 on SQLite |
| MapLibre map + viewport filtering | Complete; live browser verified |
| Native clustering and map/list sync | Complete; live browser verified |
| Private evidence upload + signed previews | Complete; live API/browser verified |
| Storage client RLS policy | Not applied on hosted Supabase (table owner restriction); direct storage reads are deny-all |
| Incident intelligence and duplicate suggestions | Complete; live API/browser verified |
| Reviewable incident relationships | Complete; live API verified |
| Infrastructure proximity / impact foundation | Complete; live API verified |
| H3 urban risk cells, trends, and exposure | Complete; live API/browser verified |
| Staff risk runs and per-cell snapshots | Complete; live API verified |
| Decision scenarios, response actions, and explicit resources | Complete; live API/browser verified |
| Bounded planning simulation and strategy comparison | Complete; live API/browser verified |
| Model registry, activation audit, and labelled evaluation framework | Complete; live API verified |
| Provenance-aware ingestion, freshness, and quality monitoring | Complete; live API/browser verified |
| Staff alerts, in-app notifications, and plan approvals | Complete; live API/browser verified |
| Reproducible NYC 311 public-data snapshot and provenance | Complete; 5,102 real records, live API/browser verified |
| Rolling-origin risk backtest vs four baselines | Complete; empirical result honestly unfavorable |
| Synthetic correlation and planning evidence | Complete; explicitly labelled and separately reported |
| Append-only validation experiments and reports | Complete; API, CLI, and `/validation` dashboard verified |
| Multi-region / multi-period NYC 311 snapshots with provenance | Complete; 4 snapshots, hashes and query metadata persisted |
| Factor diagnostics and 19-variant ablation | Complete; persisted, renormalized, paired against the full model |
| Robustness, bootstrap intervals, and sign tests | Complete; descriptive statistics, intervals reported as such |
| Candidate selection and model decision | Complete; `drop_trend` evaluated on 3 holdouts, retained unchanged, `NOT_ACTIVATED` |
| Phase 9 research report and dashboard extension | Complete; 18-section report and persisted-data-only UI |
| Controlled pilot lifecycle and separation of duties | Complete; API + browser tested on disposable DB; live Supabase refused unauthorized/empty state |
| Human-in-the-loop risk review and append-only audit | Complete; API + browser tested on disposable DB; live Supabase read-only/empty state |
| Assessment traceability and structured export | Complete; API + browser tested on disposable DB; live Supabase has no risk runs |
| Reviewer-verified correlation evaluation | Complete; API + browser tested with synthetic fixtures; not empirical ground truth |
| Metadata-only infrastructure readiness registry | Complete; API + browser tested on disposable DB; no assets fetched anywhere |
| Decision-simulation constraint audit | Complete; API/browser tested; live simulation set is empty |
| 16-category readiness scorecard and activation gate | Complete; live state `NOT_READY` (5 blocked, 1 fail, 4 not assessed) |
| Phase 10 migration, staff RLS, append-only triggers | Applied live; 11 tables, 11 policies, 5 append-only triggers verified |
| Phase 11 hashed acquisition and snapshot provenance | Complete; 3 current real snapshots with recomputed SHA-256 |
| Real NYC bridge infrastructure integration | Complete; 794 assets, 1/7 domains, metadata-only source verification |
| Human ground-truth and correlation-universe framework | Implemented/tested with synthetic fixtures; 0 operational verified records live |
| Fresh Q3 2026 external validation | Complete; Brooklyn and Manhattan evaluated, both below strongest baseline |
| Phase 11 staff RLS and append-only event guards | Applied live; 5 tables, 5 policies, 2 append-only triggers verified |
| Authoritative municipal hazard outcomes / field labels | Not included; no human-verified operational ground truth or complete correlation universe |

Phase 4 was committed and pushed as `bfc073e`
(`feat(civicflow): implement phase 4 incident intelligence`). Phase 5 is
committed as `640f173`; Phase 6 is committed as `a9d6923`; Phase 7 is committed
as `e4a3ab6`; Phase 8 is committed as `62c2e02`. Phase 9 is committed for review
without rewriting Phase 1–8 history.
