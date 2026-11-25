# Production Deployment Audit

> **Current status correction (2026-11-26 recovery sprint):** statements below
> that no deployed service was reachable reflect the original audit window only.
> Both platforms are now verified reachable by read-only HTTP:
> `https://civicflow-8dol.onrender.com/api/v1/health` (200 in this sprint) and
> `https://civic-flow-lilac.vercel.app` (200). The deployed frontend still serves
> a pre-recovery build. See `docs/deployment/PRODUCTION_VERIFICATION.md` §0.

Date: 2026-11-26
Method: direct inspection of the current worktree, Git history, tracked files,
local (untracked) environment files, and read-only queries against the
configured Supabase project. No prior agent report was treated as authoritative.

## 1. Current verified state

| Area | Verified observation | Source |
| --- | --- | --- |
| Git branch | `main` | `git branch --show-current` |
| Git status | clean, no uncommitted tracked changes | `git status --short --branch` |
| HEAD | `0cb3a0416962bddf2b290b69ecb6d158db9a8668` | `git rev-parse HEAD` |
| Upstream | `origin/main` at the same commit | `git rev-parse @{u}` |
| Remote | `https://github.com/Shri7ul/CivicFlow.git` | `git remote -v` |
| Recent history | Phase 11 (`fddb0a1`…) → Phase 12 (`7d402ce`) → Phase 13 (`c842dc3`, `935ec0f`) → Phase 14 (`3a03b5d`, `65043a7`) → Dhaka sprint (`0cb3a04`) | `git log --oneline -12` |
| Backend stack | FastAPI + SQLAlchemy 2.x + Alembic, Python 3.11 target, `uvicorn app.main:app` | `backend/pyproject.toml`, `scripts/run-backend.ps1` |
| Frontend stack | Next.js, Node 20 target | `frontend/package.json`, `.github/workflows/verify.yml` |
| Database | Supabase PostgreSQL 17.12 + PostGIS 3.3.7 | live read-only query |
| Live Alembic head | `0022_snapshot_provenance` | `select version_num from alembic_version` |
| Local code head | `0024_phase14_pilot` | `alembic heads` |
| Schema gap | `geographic_contexts`, `pilot_boundaries`, `field_observations` absent live; `pilots`, `evidence_snapshots` present | `to_regclass` queries |
| Live data | 57 public tables, 53 with RLS, 3 evidence snapshots, 6 validation datasets, 0 pilots, 0 ground-truth records | live read-only counts |
| DB role used by app config | `postgres` (privileged; RLS is advisory for this role) | `select current_user` |

### Application verified locally against the live database

Using `TestClient` with the repository's local `.env` (development profile), all
probes returned real responses with `X-Request-ID` correlation headers:

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/health` | 200 `healthy` |
| `GET /api/v1/health/database` | 200 `reachable` (real `SELECT 1`) |
| `GET /api/v1/health/ready` | 200 `ready` |
| `GET /api/v1/health/dependencies` | 503 `degraded` (see defect D1 below) |
| `GET /docs`, `GET /openapi.json` | 200 (development profile only) |

This is **local process verification**, not a deployed-service verification.

## 2. Deployment infrastructure status

| Component | Configured in repository | Verified live access | Status |
| --- | --- | --- | --- |
| Render backend | `render.yaml` now present (added by this sprint); no Dockerfile | No connected Render tool, no CLI, no API token in environment | **BLOCKED** (access), config prepared |
| Vercel frontend | `frontend/vercel.json` now present (added by this sprint) | No connected Vercel tool, no CLI, no API token in environment | **BLOCKED** (access), config prepared |
| Supabase database | Local `.env` with DSN and keys (untracked, gitignored) | Reachable, PostgreSQL 17.12 + PostGIS 3.3.7 | **REACHABLE** (dev-profile credentials) |
| GitHub Actions | `.github/workflows/verify.yml` (test/build/safety only) | Header explicitly states it never deploys and never touches production | **NO DEPLOY JOB** |
| Deployment URLs | None in tracked files; `PHASE14_BASELINE.md` records `NOT_ASSESSED` | — | **ABSENT** |

CLI audit: `gh`, `vercel`, `render`, `supabase`, `psql`, `docker` are all absent.
Connected plugins audit: no connectors installed. Environment-variable audit:
no `VERCEL_*`, `RENDER_*`, `SUPABASE_ACCESS_TOKEN`, `GH_TOKEN` or equivalent
deployment credentials are present in the shell environment.

## 3. Deployment blockers

| ID | Blocker | Severity | Evidence |
| --- | --- | --- | --- |
| B1 | No Render access | Critical | no CLI/connector/token; blueprint `render.yaml` prepared but not applied; no deployment URL |
| B2 | No Vercel access | Critical | no CLI/connector/token; `frontend/vercel.json` prepared but not applied; no deployment URL |
| B3 | No verified backup or tested restore | Critical | `docs/operations/PHASE13_BACKUP_RECOVERY.md:61-67`; no `pg_dump`, no backup artifacts, no provider verification |
| B4 | Live schema 2 revisions behind code | Critical | live DB `0022`, code head `0024`; Phase 12/14 tables absent |
| B5 | Local credentials are development-profile | High | `APP_ENV=development`, `DEBUG=true`, CORS `localhost` only in `backend/.env` |
| B6 | No deployment history / rollback artifacts | High | no platform access; `PHASE13_BACKUP_RECOVERY.md:29` records deployment rollback unavailable |

## 4. Security concerns

| ID | Concern | Assessment |
| --- | --- | --- |
| S1 | Secrets in tracked files | No tracked `.env`, private key, token or credential found. CI `repository-safety` job enforces this. |
| S2 | Secrets in untracked local files | `backend/.env` and `frontend/.env.local` contain real-format credentials; both are gitignored and must never be committed or surfaced in logs/docs. |
| S3 | `NEXT_PUBLIC_*` exposure | Only `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`; frontend config rejects anon keys containing `service_role`. No secret is public. |
| S4 | CORS | Explicit origins required in production; wildcard + credentials rejected by `Settings._validate_security`. |
| S5 | API docs in production | `/docs`, `/redoc`, `/openapi.json` disabled unless `DEBUG=true` in production. Safe by default. |
| S6 | JWT | JWKS-only verification, RS256/ES256, required `exp/iat/sub/aud/iss`; HS256 rejected. |
| S7 | RLS | 53 tables RLS-enabled, but application DB role is `postgres`, which bypasses RLS. Enforcing a least-privilege role is a provider-side prerequisite, not something code can fix. |
| S8 | Trusted hosts | `TrustedHostMiddleware` / `allowed_hosts` absent. Recommended hardening once the production hostname is known. |
| S9 | Rate limiting | In-process fixed window; adequate for a single instance, not distributed. Document as a limitation. |
| S10 | D1 defect (fixed this sprint) | `/api/v1/health/dependencies` used raw optional `SUPABASE_JWKS_URL`, causing a false `degraded` state when the URL was correctly derived from `SUPABASE_URL`. Fixed and regression-tested. |

## 5. Migration status

The full chain is linear: `0001_initial_schema` → … → `0022_snapshot_provenance`
→ `0023_phase12_geography` → `0024_phase14_pilot` (head). The live database is at
`0022`. Both outstanding migrations are additive, but `0023` contains an offline
render defect (its seed loop does not run in `--sql` mode, producing `NULL` seed
rows); online `alembic upgrade` is required. Details and verification queries
are in `PRODUCTION_MIGRATION_REVIEW.md`.

**Migration execution is BLOCKED** by B3 (no verified backup/restoration) and by
the absence of a confirmed production authorization/change window. No migration
was applied during this sprint.

## 6. Environment configuration status

Backend production validation (`backend/app/core/config.py:366-385`) requires
`DEBUG=false`, explicit `CORS_ORIGINS`, `DATABASE_URL` and `SUPABASE_URL`, and
rejects wildcard CORS with credentials. The current local `.env` is a
development profile and is **not suitable for production deployment as-is**.
Render and Vercel environment variables must be set through their dashboards;
no secret values are recorded in this repository or these documents.

## 7. Deployment readiness verdict

**DEPLOYMENT BLOCKED.** Neither Render nor Vercel access exists in this
environment, and no verified backup makes the pending production migration
unsafe to apply. The repository itself is buildable and testable, and the
Supabase project is reachable for read-only verification, but no deployed
artifact can be produced or verified from this environment.

## 8. Recommended deployment sequence

1. Confirm provider backups and PITR for the Supabase project; record the
   backup identifier and timestamp; perform a restore drill in an isolated
   database. Until then, do not migrate.
2. Obtain Render and Vercel access (dashboard role, CLI token, or connected
   integration) and confirm the existing project/service identities. Do not
   create duplicate services.
3. Apply `render.yaml` and `vercel.json` (added by this sprint) to the existing
   services after reconciling them with the dashboard settings. Set all secret
   environment values through the platform dashboards, with `sync: false` where
   applicable.
4. Run `alembic upgrade head` online against the verified target database in a
   change window; execute `PRODUCTION_MIGRATION_REVIEW.md` verification queries.
5. Deploy backend, then frontend; verify `/api/v1/health`, `/api/v1/health/ready`
   and `/api/v1/health/dependencies` (expected `operational` with derived JWKS).
6. Run `backend/scripts/production_smoke_test.py` against the live URLs.
7. Record actual URLs, deployment IDs and timestamps in
   `PRODUCTION_VERIFICATION.md` and `PRODUCTION_DEPLOYMENT_REPORT.md`.

The Dhaka pilot remains NOT READY throughout; see `PHASE14_FINAL_REPORT.md`.
