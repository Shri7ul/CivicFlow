# CivicFlow Backend — Render FREE Web Service Deployment Guide

This is an exact, evidence-based guide for a human deploying the CivicFlow
FastAPI backend on Render's FREE Web Service. Every value below was verified
against the repository at commit `1a6142c` and after this sprint's fixes.
No deployment was performed by the agent that wrote this guide.

## Root cause of the previous failed build

The previous Render log showed:

```text
Using Python version 3.14.10 (default)
Running build command 'pip install -r requirements.txt'
ERROR: Could not open requirements file: [Errno 2] No such file or directory
```

Verified causes:

1. At commit `1a6142c` there was **no `requirements.txt` anywhere in the
   repository** (neither root nor `backend/`). The backend declared its
   dependencies only in `backend/pyproject.toml`. Any `pip install -r
   requirements.txt` was therefore guaranteed to fail, regardless of the
   configured root directory.
2. Render used Python 3.14.10 and `pip install -r requirements.txt`, while the
   checked-in `render.yaml` declared `PYTHON_VERSION=3.11` and
   `pip install -e .`. This proves the Render service was **not using the
   repository blueprint**; it was using dashboard/default settings. Editing
   `render.yaml` alone will not change an already-created service — the
   dashboard settings of that service must be updated, or the blueprint must be
   applied to it.
3. The root directory was apparently not `backend`. Setting it is still
   required, but it would not have fixed the missing file by itself.
4. The checked-in blueprint used `plan: starter`, not the target FREE plan.

Fixes applied in this repository:

- Added `backend/requirements.txt`, an exact mirror of
  `[project].dependencies` in `backend/pyproject.toml` (11 packages, verified
  identical, development-only `pytest` excluded).
- Added `backend/.python-version` containing `3.11`.
- Corrected `render.yaml` to `plan: free`, `rootDir: backend`,
  `buildCommand: python -m pip install -r requirements.txt`, pinned
  `PYTHON_VERSION=3.11`, and safe explicit defaults for the non-secret
  Supabase fields.
- Corrected `docs/deployment/PRODUCTION_DEPLOYMENT_AUDIT.md`, which had become
  stale about the existence of `render.yaml`.

---

## 1. Repository selection

| Item | Exact value |
| --- | --- |
| GitHub repository | `https://github.com/Shri7ul/CivicFlow` |
| Branch | `main` |
| Root Directory | `backend` |
| Service type | Web Service (not Static Site, not Background Worker) |

The FastAPI application object is `app.main:app` in `backend/app/main.py:89`.
Uvicorn must run with the working directory set to `backend` so that the
`app` package is importable.

## 2. Render configuration

Enter these values in the Render dashboard (or apply `render.yaml` as a
blueprint to the **existing** service and verify the result):

| Setting | Exact value |
| --- | --- |
| Name | `civicflow-api` |
| Runtime | `Python 3` (native Python, no Docker) |
| Region | `singapore` (or any region supported by the Free plan) |
| Root Directory | `backend` |
| Build Command | `python -m pip install -r requirements.txt` |
| Start Command | `python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | `Free` |
| Health Check Path | `/api/v1/health` |
| Branch | `main` |
| Auto Deploy | optional; enable only after the first successful deploy |

`PYTHON_VERSION=3.11` must be set as an environment variable (see below) so
Render does not fall back to its 3.14 default. `backend/.python-version` is
also present for local tooling consistency.

The `alembic upgrade head` prefix is mandatory: without it a deploy can serve
an older schema where `workforce_notifications` and other workforce tables do
not exist. **If the existing Render service was configured manually, update
its Start Command in the Render dashboard as well** — editing `render.yaml`
alone does not change a service that was not created from the blueprint.
Notification reads now degrade to an empty inbox as a safety net, but the
migration step is still required for the full workforce workflow.

### Why Python 3.11

- `backend/pyproject.toml` declares `requires-python = ">=3.11"`.
- `.github/workflows/verify.yml` runs the entire backend suite on Python 3.11.
- Every dependency declares support for 3.11; current binary wheels for
  `h3`, `psycopg-binary` and `cryptography` were confirmed to include `cp311`.
- Render's 3.14 default is outside the project's tested matrix. Pinning 3.11
  produces a reproducible build. No dependency versions were changed.

## 3. Environment variables

Set these in the Render service's **Environment** tab. Never paste secret
values into Git, documentation, or deployment logs.

| Variable | Required | Value type | Instructions | Secret |
| --- | --- | --- | --- | --- |
| `PYTHON_VERSION` | Yes | fixed `3.11` | Prevents Render's 3.14 default | No |
| `APP_ENV` | Yes | `production` | Enables production validation and hardening | No |
| `DEBUG` | Yes | `false` | Startup validation rejects `true` in production | No |
| `API_V1_PREFIX` | No (default `/api/v1`) | string | Keep default | No |
| `LOG_LEVEL` | No (default `INFO`) | enum | `INFO` recommended | No |
| `SECURITY_HEADERS_ENABLED` | No (default `true`) | boolean | Keep `true` | No |
| `API_DOCS_ENABLED` | No (default `true`) | boolean | Set `false`; production hides docs anyway | No |
| `RATE_LIMIT_ENABLED` | No | boolean | `true` recommended | No |
| `CORS_ORIGINS` | **Yes in practice** | comma-separated exact origins | Actual Vercel HTTPS origin only; never `*` with credentials | No |
| `CORS_ALLOW_CREDENTIALS` | No (default `true`) | boolean | Keep `true` | No |
| `DATABASE_URL` | **Yes** | Supabase PostgreSQL DSN | Use the project's pooler connection string; app normalizes `postgres://`/`postgresql://` to `postgresql+psycopg://` | **Yes** |
| `SUPABASE_URL` | **Yes** | `https://<project-ref>.supabase.co` | Startup validation requires it; JWKS/issuer are derived from it | No |
| `SUPABASE_ANON_KEY` | No | public anon JWT | Only if frontend-related server calls need it | Yes (treat as sensitive) |
| `SUPABASE_SERVICE_ROLE_KEY` | No* | service-role JWT | *Required only for private evidence-storage endpoints; omit if not used | **Yes** |
| `SUPABASE_JWT_AUDIENCE` | No (default `authenticated`) | string | Keep default; non-empty required | No |
| `SUPABASE_JWT_ISSUER` | No | URL | Leave unset; derived from `SUPABASE_URL` | No |
| `SUPABASE_JWKS_URL` | No | URL | Leave unset; derived from `SUPABASE_URL` | No |
| `SUPABASE_STORAGE_BUCKET` | No (default `incident-evidence`) | string | Keep default | No |
| `DATABASE_SSLMODE` | No | string | Leave unset; production defaults to `require` | No |
| `ALEMBIC_DATABASE_URL` | No (web service) | PostgreSQL DSN | Migration-only variable used by Alembic, not by the web app | **Yes** if set |

Startup-enforced rules (from `backend/app/core/config.py`):

- Production requires `DEBUG=false`, non-empty `CORS_ORIGINS`, `DATABASE_URL`
  and `SUPABASE_URL`.
- `CORS_ORIGINS=*` together with `CORS_ALLOW_CREDENTIALS=true` is rejected at
  startup.
- `SUPABASE_URL` must be HTTPS.
- A blank `DATABASE_URL` in production raises a validation error and the
  process exits — this is intentional; do not bypass it.

`HOST` and `PORT` are not needed: Render injects `$PORT` and the start command
uses it. `get_settings().host/port` are not read by the application.

## 4. Deployment

1. Log in to Render → **Dashboard** → **New +** → **Web Service**.
2. Connect the GitHub account and select `https://github.com/Shri7ul/CivicFlow`.
   If a `civicflow-api` service already exists, open **that service** and edit
   its settings instead of creating a duplicate.
3. Select branch `main` and set **Root Directory** to `backend`.
4. Select Runtime `Python 3` and Instance Type `Free`.
5. Enter the Build Command and Start Command exactly as in section 2.
6. Set **Health Check Path** to `/api/v1/health`.
7. Add every environment variable from section 3 in the **Environment** tab.
   Use Render's secret/protected mechanism for `DATABASE_URL` and the Supabase
   keys.
8. Click **Create Web Service** (or **Save Changes** on the existing service).
9. Watch **Logs** in the Render dashboard. A successful build shows the
   requirements being installed, then `Uvicorn running on ...`.
10. If using the blueprint instead: Dashboard → **New +** → **Blueprint** →
    point at this repository → select `render.yaml` → review that the target is
    the existing service, set the `sync: false` values during the flow, then
    apply. Verify the resulting dashboard values match section 2.

Do not run migrations, seed data, reset Supabase, or activate the pilot as
part of this deployment. Application migrations are a separate, authorized
operation.

## 5. Health verification

All paths are prefixed with `/api/v1` because `main.py:84` mounts the health
router at `/health` under the `/api/v1` API prefix.

| Request | Expected response |
| --- | --- |
| `GET https://<render-url>/api/v1/health` | `200 {"status":"healthy", ...}` — process liveness; this is Render's configured health check |
| `GET https://<render-url>/api/v1/health/database` | `200 {"status":"healthy","database":"reachable"}` if Supabase is reachable |
| `GET https://<render-url>/api/v1/health/ready` | `200 {"status":"ready", ...}`; `503` if DB is not configured or unreachable |
| `GET https://<render-url>/api/v1/health/dependencies` | `200 {"status":"operational","auth_verification_configured":true}` in a fully configured production deploy |
| `GET https://<render-url>/docs` | `404` in production (API docs disabled) |
| `GET https://<render-url>/api/v1/auth/me` | `401` without a bearer token |

Every response should include the `X-Request-ID` header. Security headers
(`X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control`, CSP) are present;
HSTS is added when Render's HTTPS proxy supplies `X-Forwarded-Proto: https`.

A repeatable check is available:

```bash
cd backend
python scripts/production_smoke_test.py --base-url https://<render-url>
```

This script is read-only: it performs no writes, creates no incidents, ground
truth, authorizations or pilots, and never activates a pilot.

## 6. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Could not open requirements file: 'requirements.txt'` | Build ran from the wrong directory, or an older commit is deployed | Set Root Directory to `backend`; confirm `backend/requirements.txt` is present on `main`; trigger a fresh deploy |
| `ERROR: Could not find a version that satisfies the requirement ...` | Wrong `PYTHON_VERSION` or stale pip | Pin `PYTHON_VERSION=3.11`; the build command installs directly from `requirements.txt` |
| Python 3.14.10 still shown in logs | Service is not using the blueprint / env var missing | Add `PYTHON_VERSION=3.11` in the Render Environment tab and redeploy |
| `ModuleNotFoundError: No module named 'app'` | Working directory is not `backend`, or start command changed | Root Directory `backend`; start command must be exactly `python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Import error / `ValidationError` at startup with `DATABASE_URL is required in production` | Missing or blank `DATABASE_URL` | Set the Supabase DSN in the Render Environment tab; do not set `DEBUG=true` to bypass |
| `CORS_ORIGINS cannot contain '*' when CORS_ALLOW_CREDENTIALS is true` | Wildcard CORS | Use the exact Vercel origin(s), comma-separated |
| `health/database` or `ready` returns 503 | Supabase unreachable, wrong DSN, SSL or network policy | Verify DSN, that the Supabase project is active, and that `sslmode=require` is accepted; check Render logs |
| Browser CORS failure | Vercel origin absent from `CORS_ORIGINS` | Add the exact origin (scheme + host, no trailing slash) and redeploy the backend |
| `401` on authenticated calls | Missing/invalid Supabase token or wrong `SUPABASE_URL` / audience | Confirm `SUPABASE_URL` and `SUPABASE_JWT_AUDIENCE`; verify the token was issued by that project |
| Render health check fails while app logs show requests | Wrong health path or cold start | Use `/api/v1/health`; allow for Free-instance cold starts of up to about a minute |
| Free instance cold starts / timeouts | Normal Free-plan behavior | Use `/api/v1/health` as a liveness-only check; do not interpret a slow first request as a database failure |

## 7. Supabase connection

- The application accepts `postgres://` or `postgresql://` DSNs and rewrites
  them to `postgresql+psycopg://` (`backend/app/db/session.py:29-41`). The
  installed driver is `psycopg[binary]`; psycopg2 is not installed.
- In production, if the URL has no `sslmode` query parameter, the app adds
  `sslmode=require` (`session.py:44-63`). A URL-level `?sslmode=...` takes
  precedence.
- Connection settings: `connect_timeout=5s`, `pool_size=5`, `max_overflow=10`,
  `pool_timeout=30s`, `pool_recycle=1800s`, `pool_pre_ping=True`. These suit a
  Supabase pooler endpoint on a single Render instance.
- Recommended: use the Supabase **pooler** connection string (port 6543) for
  the web service; reserve the direct connection (port 5432) for migrations
  via `ALEMBIC_DATABASE_URL`.
- PostGIS 3.3.7 was verified on the configured project. No database object is
  created at application startup; migrations remain a separate step.
- Safety: do not reset, recreate or delete the Supabase project; do not run
  migrations as part of the web deploy; do not write production data during
  verification.

## 8. Vercel integration

The future Vercel frontend must be allowlisted by the backend:

1. Obtain the **actual** Vercel production URL after the frontend is deployed.
   No domain is fabricated in this guide.
2. In Render → Environment, set `CORS_ORIGINS` to that exact HTTPS origin. For
   multiple origins, use a comma-separated list with no spaces.
3. Keep `CORS_ALLOW_CREDENTIALS=true` and never use `*`.
4. Save and redeploy the backend; CORS configuration is read at startup
   (`backend/app/main.py:74-80`).
5. In the Vercel project, set `NEXT_PUBLIC_API_BASE_URL` to the Render backend
   origin. Do not expose service-role keys through any `NEXT_PUBLIC_*` variable.

## 9. Rollback

- In Render, open the service → **Deployments** → select the last successful
  deploy → **Roll back to this deploy** (or redeploy that commit). This changes
  only the application artifact.
- Do **not** reset, delete or rewrite Supabase data as a rollback mechanism.
- If a migration was applied as part of a release, roll the application back
  only to a version compatible with that schema. Migration recovery is
  described in `docs/deployment/PRODUCTION_MIGRATION_REVIEW.md` and must be
  explicitly authorized.
- After rollback, re-run the health verification in section 5.

## 10. Deployment checklist

- [ ] Repository is `https://github.com/Shri7ul/CivicFlow`, branch `main`.
- [ ] Existing `civicflow-api` service edited (no duplicate created).
- [ ] Root Directory = `backend`.
- [ ] Runtime = Python 3; Instance Type = Free; Region selected.
- [ ] `PYTHON_VERSION=3.11` present in the Render Environment tab.
- [ ] Build Command = `python -m pip install -r requirements.txt`.
- [ ] Start Command = `python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- [ ] Health Check Path = `/api/v1/health`.
- [ ] `APP_ENV=production`, `DEBUG=false`, `API_DOCS_ENABLED=false`.
- [ ] `DATABASE_URL` and `SUPABASE_URL` set; Supabase keys set if used.
- [ ] `CORS_ORIGINS` = exact Vercel origin, never `*`.
- [ ] No secrets in Git, docs or logs.
- [ ] Build and deploy logs reviewed; no `requirements.txt` error.
- [ ] `/api/v1/health`, `/api/v1/health/database`, `/api/v1/health/ready`,
      `/api/v1/health/dependencies` verified.
- [ ] `/docs` returns 404; `/auth/me` returns 401.
- [ ] Smoke test executed and results recorded.
- [ ] No migrations run, no pilot activated, no ground truth created.
