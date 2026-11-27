# Render Configuration Reference — CivicFlow Backend

Compact, verified reference. This file must match `render.yaml` and the
backend source. Full instructions are in `RENDER_WEB_SERVICE_DEPLOYMENT.md`.

Exact service values (identical to `render.yaml`):

```text
plan: free
rootDir: backend
buildCommand: python -m pip install -r requirements.txt
startCommand: python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /api/v1/health
PYTHON_VERSION: 3.11
```

## Service

| Key | Value |
| --- | --- |
| Repository | `https://github.com/Shri7ul/CivicFlow` |
| Branch | `main` |
| Root Directory | `backend` |
| Service type | Web Service, native Python (no Docker) |
| Name | `civicflow-api` |
| Plan | `free` |
| Region | `singapore` |
| Build Command | `python -m pip install -r requirements.txt` |
| Start Command | `python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/v1/health` |
| Python version | `3.11` (env `PYTHON_VERSION`, also `backend/.python-version`) |

## Dependencies

`backend/requirements.txt` mirrors `[project].dependencies` in
`backend/pyproject.toml` exactly (11 runtime packages; no `pytest`). Verified
identical by direct comparison. `pip install -r requirements.txt --dry-run`
resolves successfully. No dependency versions were changed.

## Environment variables

Required in production (startup-enforced by `Settings._validate_security`):

| Variable | Value | Secret |
| --- | --- | --- |
| `PYTHON_VERSION` | `3.11` | No |
| `APP_ENV` | `production` | No |
| `DEBUG` | `false` | No |
| `DATABASE_URL` | Supabase PostgreSQL DSN | **Yes** |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | No |
| `CORS_ORIGINS` | Exact Vercel HTTPS origin(s), comma-separated; never `*` | No |

Safe explicit defaults set in `render.yaml`:

| Variable | Value |
| --- | --- |
| `API_V1_PREFIX` | `/api/v1` |
| `HOST` | `0.0.0.0` |
| `LOG_LEVEL` | `INFO` |
| `SECURITY_HEADERS_ENABLED` | `true` |
| `API_DOCS_ENABLED` | `false` |
| `RATE_LIMIT_ENABLED` | `true` |
| `CORS_ALLOW_CREDENTIALS` | `true` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `SUPABASE_STORAGE_BUCKET` | `incident-evidence` |

Secret, set only in the Render dashboard if used:

| Variable | Purpose |
| --- | --- |
| `SUPABASE_ANON_KEY` | Public anon key; treat as sensitive |
| `SUPABASE_SERVICE_ROLE_KEY` | Private evidence-storage operations only |
| `ALEMBIC_DATABASE_URL` | Migration-only; not needed by the web service |

Optional overrides: `SUPABASE_JWT_ISSUER`, `SUPABASE_JWKS_URL`,
`DATABASE_SSLMODE` (production default `require`). Leave unset unless there is
a specific reason.

`HOST`/`PORT` are not read by the app; Render supplies `$PORT` to the start
command.

## Health and readiness

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health` | Liveness, always 200; Render health check target |
| `GET /api/v1/health/database` | Real `SELECT 1`; 503 if not configured or unreachable |
| `GET /api/v1/health/ready` | 200 only when DB is configured and reachable |
| `GET /api/v1/health/dependencies` | 200 `operational` when DB and derived JWKS URL are present |

`/docs`, `/redoc` and `/openapi.json` are disabled in production and return 404.
Every response carries `X-Request-ID`.

## Supabase connection

- Accepts `postgres://` / `postgresql://`; normalized to
  `postgresql+psycopg://` (`psycopg[binary]`, not psycopg2).
- TLS: `sslmode=require` added in production when not present in the URL.
- Pool: size 5, max overflow 10, timeout 30s, recycle 1800s, pre-ping enabled.
- Use the Supabase **pooler** endpoint for the web service; direct endpoint is
  for migrations. No DB writes or migrations occur during a web deploy.
- Verified on the configured project: PostgreSQL 17.12, PostGIS 3.3.7.

## CORS

- Exact scheme + host of the deployed Vercel frontend, e.g.
  `https://<actual-vercel-domain>` — no fabricated domain here.
- Multiple origins: comma-separated, no spaces.
- Wildcard `*` with `CORS_ALLOW_CREDENTIALS=true` is rejected at startup.
- CORS is configured at application startup; changing it requires a Render
  redeploy.

## Consistency note

Values here are taken from `render.yaml`, `backend/pyproject.toml`,
`backend/app/core/config.py`, `backend/app/db/session.py`, `backend/app/main.py`
and `backend/app/api/v1/endpoints/health.py`. If any value changes, update all
of these files together.
