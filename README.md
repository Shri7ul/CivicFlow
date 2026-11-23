# CivicFlow

**Urban Impact & Response Intelligence**

CivicFlow is a full-stack platform for modeling interconnected civic incidents,
understanding urban risk, and coordinating municipal response. The repository
currently contains **Phase 0** (application foundation), **Phase 1** (database
architecture + authentication/authorization), **Phase 1.6** (security hardening),
**Phase 2** (incident reporting and lifecycle management), **Phase 3**
(spatial map, clustering, and private evidence), and **Phase 4** (explainable
incident intelligence).

Phase 4 adds deterministic correlation and duplicate suggestions, reviewable
relationship records, PostGIS infrastructure proximity, and dependency-aware
impact foundations. Every suggestion carries reasons, confidence, and explicit
limitations; nothing is auto-merged. Risk scoring, scenario simulation,
notifications, and authoritative municipal dataset ingestion remain future work. See [docs/PROGRESS.md](docs/PROGRESS.md) for current status,
verification evidence, and known boundaries.

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
    providers.tsx             Auth provider boundary
  src/components/auth/        Provider, guard, form, navigation, shell
  src/components/map/         Map view and report location picker
  src/components/incidents/   Cards, badges, and evidence gallery
  src/lib/api/                Typed API client and auth/profile calls
  src/lib/auth/               Route safety, role labels, cookie helper
  src/lib/supabase/           Browser client and public configuration
  src/proxy.ts                Optimistic dashboard/incident route protection

backend/
  app/
    api/v1/endpoints/         health, auth, admin, incidents, departments
    auth/                     JWT verification and FastAPI dependencies
    core/                     Settings, logging, middleware, error handling
    db/                       Engine/session factory and health check
    models/                   SQLAlchemy model registry (15 tables)
    schemas/                  Pydantic request/response schemas
    services/profiles.py      Provisioning, profile update, audited roles
    services/incidents.py     Reporting, visibility, lifecycle, serialization
    services/evidence.py      Evidence validation, upload, signed URL flow
    services/storage.py       Server-only Supabase Storage adapter
    services/intelligence.py  Correlation, duplicate, infrastructure, impact
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
`0008_confidence_check_name`, PostGIS 3.3.7 is installed, the RLS/ACL matrix has
been exercised transactionally and with isolated real Auth users, and private
Storage upload/signed-download was verified end to end. See
`backend/docs/auth-and-rls.md` for database setup and policy details,
`backend/docs/incidents.md` for the lifecycle contract,
`backend/docs/spatial.md` for the viewport API, and
`backend/docs/evidence.md` for the evidence/storage boundary.

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

The configured Supabase project was validated on **2026-11-23**:

- Database and Auth project references match between backend and frontend.
- Auth health endpoint returned `200`; JWKS returned a valid ES256 signing key.
- PostgreSQL 17.12 was reachable over TLS through the configured pooler.
- PostGIS 3.3.7 is installed in the `public` schema.
- Alembic is at `0008_confidence_check_name`; all 15 application tables, 19
  application RLS policies, 9 triggers, 17 foreign keys, 6 unique constraints,
  and 4 GIST indexes exist. The private `incident-evidence` bucket exists with
  a 10 MB limit and JPEG/PNG/WebP allowlist.
- RLS was exercised with synthetic JWT claims inside a rolled-back transaction
  for anonymous, Citizen, Worker, and Admin behavior. No validation rows were
  persisted. `storage.objects` has no policy for this bucket; direct
  authenticated Storage reads are denied (verified `404`), while backend-issued
  signed URLs work.
- Live least-privilege hardening removed inherited `TRUNCATE`, `REFERENCES`,
  `TRIGGER`, and `MAINTAIN` grants from `anon`/`authenticated`; `service_role`
  was intentionally left unchanged. Anonymous now has no application-table
  grants. After `0008`, authenticated has SELECT on all 15 application tables,
  INSERT on incidents and scenarios, column UPDATE on `profiles.full_name/phone`
  only, and no direct INSERT on `incident_evidence` or
  `incident_relationships`.
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
dependency-path labeling.

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
suggestion-vs-inference labels.

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
| ACL least privilege | Applied live through `0008_confidence_check_name`; verified directly |
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
| Risk / scenarios / notifications / authoritative asset ingestion | Not implemented (future phases) |

Phase 4 incident intelligence is the current endpoint. Phase 3 was committed and
pushed as `69cf003` (`feat(civicflow): complete phase 3 spatial intelligence`);
the Phase 4 changes are intentionally uncommitted in the working tree.
