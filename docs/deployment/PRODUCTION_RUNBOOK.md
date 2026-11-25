# Production Runbook

> **Current status correction (2026-11-26 recovery sprint):** platform access is
> still unavailable to the agent, but the deployed services are live and
> reachable: backend `https://civicflow-8dol.onrender.com`, frontend
> `https://civic-flow-lilac.vercel.app`. The deployed build predates the
> recovery fixes. Verify current service identity in the dashboards before
> following these procedures. See `docs/deployment/PRODUCTION_VERIFICATION.md` §0.

Status: **PROCEDURES PREPARED / PLATFORMS NOT ACCESSED FROM THIS ENVIRONMENT**

This runbook describes how an operator with authorized Render, Vercel and
Supabase access runs and recovers CivicFlow. No secret value is recorded here.

## 1. Service inventory (to be confirmed in dashboards)

| Component | Intended platform | Repository configuration | Actual URL |
| --- | --- | --- | --- |
| API | Render web service `civicflow-api` | `render.yaml` (root `backend`, Python 3.11, `uvicorn app.main:app`) | Not available — no Render access |
| Frontend | Vercel Next.js project | `frontend/vercel.json` (project root directory must be `frontend/`) | Not available — no Vercel access |
| Database | Supabase PostgreSQL + PostGIS | `backend/.env` (local, gitignored) | Project ref `wtkrvjnqsdcilvsocayl` (identifier only) |

Before any deployment, confirm these identities in the platform dashboards.
Do not create duplicate services or projects.

## 2. Deploy sequence

1. Confirm backup/PITR and restore evidence (see `PRODUCTION_MIGRATION_REVIEW.md`).
2. Apply migrations online: `cd backend && alembic upgrade head`.
3. Verify the migration queries in `PRODUCTION_MIGRATION_REVIEW.md` section 5.
4. Deploy the backend: Render builds from `backend/`, starts with
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check
   `/api/v1/health`.
5. Verify backend: `python scripts/production_smoke_test.py --base-url <render-url>`.
6. Deploy the frontend: Vercel installs with `npm ci` and builds with
   `npm run build` from the `frontend/` root directory.
7. Verify the site over HTTPS and re-run the smoke test.
8. Record deployment IDs, timestamps and URLs in `PRODUCTION_VERIFICATION.md`.

Environment variables with `sync: false` in `render.yaml` must be set in the
Render dashboard: `CORS_ORIGINS` (exact Vercel origin, never `*`),
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_AUDIENCE`,
`SUPABASE_STORAGE_BUCKET`. Vercel needs `NEXT_PUBLIC_API_BASE_URL`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Never add
`NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` or any private key.

## 3. Inspect logs

- **Backend (Render):** service page → *Logs* for build and runtime output.
  Every request emits a structured line containing `request_id`. Correlate a
  user-reported error by asking for the `X-Request-ID` response header.
- **Frontend (Vercel):** project → *Deployments* → select deployment → *Build
  Logs* and *Runtime Logs*. Failed builds show the failing `npm run build` step.
- **Database (Supabase):** dashboard → *Database* for health, connections and
  slow queries. Read-only SQL checks can also be run from the dashboard.
- **CI:** GitHub repository → *Actions* → `verify` workflow for backend tests,
  Alembic single-head check, frontend typecheck/lint/test/build and repository
  safety checks. The workflow does not deploy or touch the database.

## 4. Diagnose failures

| Symptom | Check | Likely cause / action |
| --- | --- | --- |
| `/health/ready` 503 | `/api/v1/health/database` | Database unreachable or `DATABASE_URL` missing; verify Render env and Supabase health. |
| `/health/dependencies` 503 `auth_verification_configured:false` | `SUPABASE_URL` and derived JWKS URL | The effective JWKS URL is derived from `SUPABASE_URL`; a raw override is optional. Verify `SUPABASE_URL` is set. This sprint fixed a false-negative check. |
| 401 on protected API | Frontend anon key / token | Confirm Supabase sign-in succeeded and the bearer token is forwarded; do not weaken auth. |
| CORS error in browser | `CORS_ORIGINS` on Render | Must list the exact Vercel origin; wildcard with credentials is rejected at startup. |
| Frontend API 404 | `NEXT_PUBLIC_API_BASE_URL` | Must point to the deployed Render origin including `/api/v1` as configured by the client. |
| Migration failure | `select version_num from alembic_version` | Stop further deploys; follow section 6. Do not hand-edit the version table. |
| Rate limit 429 | `Retry-After` header | In-process limiter; multiple replicas have independent counters. Scale with care. |

## 5. Rollback

- **Frontend:** Vercel dashboard → *Deployments* → choose the last healthy
  deployment → *Promote to Production*. No repository change is needed.
- **Backend:** Render dashboard → redeploy the previous known-good commit or
  use the service's rollback control. Keep the database compatible: do not
  roll the API back past a migration it does not understand.
- **Application data:** Phase 14 shutdown records preserve counts and never
  delete evidence, audits, provenance, decisions or incidents. See
  `docs/operations/PHASE14_ROLLBACK.md`.

## 6. Failed migration recovery

1. Stop application deploys immediately.
2. Record the exact `alembic_version` value and the failing revision.
3. If the database is at an intermediate state, use the reviewed `downgrade()`
   path from `PRODUCTION_MIGRATION_REVIEW.md` **only if no production data has
   been written to the new schema**.
4. If data was written, do not downgrade; restore the verified backup in an
   isolated environment, validate it, then re-apply the migration in a change
   window.
5. Never reset, recreate or delete the Supabase project, and never delete
   production data as a shortcut.

## 7. Smoke test

```bash
cd backend
python scripts/production_smoke_test.py --base-url https://<render-url>
# Optional read-only authenticated checks (token supplied by operator):
CIVICFLOW_SMOKE_TOKEN=<read-only-token> \
  python scripts/production_smoke_test.py --base-url https://<render-url>
```

The script only performs `GET`/`OPTIONS` requests. It never creates incidents,
ground truth, authorizations or pilots, and never activates a pilot. An
authenticated check expecting `ready_for_activation: false` is a safety assertion:
if it ever returns `true`, treat that as a critical incident and stop the pilot.

## 8. Escalation

Any of the following requires explicit human authorization: applying migrations
`0023`/`0024`, creating production credentials, granting a least-privilege DB
role, approving a boundary, selecting or activating a Dhaka pilot, and
promoting any observation to ground truth.
