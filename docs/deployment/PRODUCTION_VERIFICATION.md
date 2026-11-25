# Production Verification Record

Verification window: 2026-11-25T19:30Z–19:38Z (2026-11-26 01:30–01:38 UTC+06:00).
Repository state during verification: branch `main`, HEAD
`0cb3a0416962bddf2b290b69ecb6d158db9a8668` (plus the uncommitted changes made
by this sprint, listed in the final report).

This record distinguishes **live infrastructure evidence** from **local
verification**. The original 2026-11-25 window below is retained as a
point-in-time record; the update immediately following supersedes its claims
about deployment availability.

## 0. Recovery sprint update — 2026-11-26

**The deployment is live.** The original statement "no deployed Render or
Vercel service was reachable, so no production HTTP verification was possible"
was true of that verification window and is **no longer true**.

| Check | Result |
| --- | --- |
| `https://civic-flow-lilac.vercel.app` | **200**; real rendered CivicFlow page with CSP/HSTS headers |
| `https://civicflow-8dol.onrender.com/api/v1/health` | **200** `{"status":"healthy","environment":"production","version":"v1"}` observed during this sprint's read-only audit |
| `GET /api/v1/health/dependencies` | **200** `database: reachable`, `auth_verification_configured: true`, build `0.11.0` |
| `GET /docs` | **404** (API docs correctly disabled in production) |
| Repeat probe of the backend during this sprint | Render Free **cold-start interstitial** (service waking). This is a platform behaviour on the free plan, not an application failure; retry after wake. |
| Live frontend content | Still serves the **pre-recovery build** ("Phase 13", "Phase 5", "35 tables"). The fixes in this sprint are local and require a redeploy. |

**Corrected verdict for the current state:** deployed services are **REACHABLE
and PARTIALLY VERIFIED** (read-only HTTP only). They are **NOT YET VERIFIED
AGAINST THIS SPRINT'S CODE**, because no Render/Vercel redeploy was performed
by the agent. No authenticated production request, browser E2E, production
database query, migration, or data write was performed.

## 1. Verified: Supabase (live, read-only) — historical window

| Check | Result |
| --- | --- |
| Connectivity over TLS (sslmode=require) | OK |
| PostgreSQL server version | 17.12 |
| PostGIS | 3.3.7 (GEOS 3.14.1, PROJ 9.7.1) |
| `alembic_version` | `0022_snapshot_provenance` |
| Public tables | 57 |
| RLS-enabled tables | 53 |
| `pilots` | 0 rows |
| `evidence_snapshots` | 3 rows |
| `validation_datasets` | 6 rows |
| `ground_truth_records` | 0 rows |
| `geographic_contexts` | absent (migration 0023 pending) |
| Phase 14 tables | absent (migration 0024 pending) |
| DB role | `postgres` (privileged; RLS enforcement requires a least-privilege role) |

No write, migration, reset, delete or backup operation was performed.

## 2. Verified: application locally against the live database

Started with `uvicorn app.main:app` on `127.0.0.1:8123` using the local
development-profile `.env`. All checks are read-only.

| Check | Result |
| --- | --- |
| `GET /api/v1/health` | 200 `healthy`, environment `development` |
| `GET /api/v1/health/database` | 200 `reachable` (real `SELECT 1`) |
| `GET /api/v1/health/ready` | 200 `ready` |
| `GET /api/v1/health/dependencies` | 200 `operational`; `auth_verification_configured: true` after the fix in this sprint (was 503 before the fix) |
| `X-Request-ID` response header | present on every response |
| `GET /docs`, `/openapi.json` | 200 in development profile (expected); production config disables these |
| Unauthenticated `GET /api/v1/auth/me` | 401 |
| CORS preflight from untrusted origin | 400, no `Access-Control-Allow-Origin` |
| `python scripts/production_smoke_test.py --base-url http://127.0.0.1:8123 --expected-env development` | 11 passed, 0 failed |

## 3. Verified: Phase 14 control plane integrity

Computed from an empty schema (no seeded evidence or attestations):

| Check | Result |
| --- | --- |
| Protocol | `phase14-final-gate-v1` |
| Overall | `NOT_READY` |
| `ready_for_activation` | `false` |
| Categories | 21 |
| Blockers | 21 |
| Dhaka model readiness | `RESEARCH_ONLY` |

No pilot was created, approved or activated. No ground truth was promoted.

## 4. Verified: repository safety

| Check | Result |
| --- | --- |
| Tracked `.env` files | none |
| Tracked private keys (`*.pem`, `*.key`, `*.p12`, `*.pfx`) | none |
| Hard-coded `service_role` literals in source | none (CI enforces) |
| Deployment secrets in documentation | none |
| CI workflow | test/build/safety only; explicitly never deploys or touches production |

## 5. Verified: test suites and build

| Command | Result |
| --- | --- |
| `python -m pytest` (backend) | 305 passed, 2 warnings |
| `npm run typecheck` (frontend) | passed |
| `npm run lint` (frontend) | passed |
| `npm test` (frontend) | 30 files, 96 tests passed |
| `npm run build` (frontend) | passed; static + partial-prerender routes generated |
| `python -m alembic heads` | one head (`0024_phase14_pilot`) |
| Offline SQL render `alembic upgrade head --sql` | succeeds; 0024 segment has 11 CREATE TABLE, 11 RLS statements, 0 INSERTs |

## 6. NOT verified / blocked

| Item | Reason |
| --- | --- |
| Render backend deployment of *this sprint's code* | No connected Render tool, CLI or API token; live service exists but was not redeployed by the agent |
| Vercel frontend deployment of *this sprint's code* | No connected Vercel tool, CLI or API token; live site exists but still serves the pre-recovery build |
| Production backend URL | `https://civicflow-8dol.onrender.com` (verified reachable; see section 0) |
| Production frontend URL | `https://civic-flow-lilac.vercel.app` (verified reachable; see section 0) |
| Browser-based E2E (login, navigation, console errors) | No browser automation with a real account was executed; only read-only HTTP GETs |
| Authenticated API E2E | No authorized test token/account; none was created |
| Backup existence and restore drill | No `pg_dump`, no provider access, no backup artifact |
| Migration 0023/0024 applied to live DB | Blocked by unverified backup and missing authorization |
| RLS enforcement as non-superuser | Application config uses `postgres`; requires provider-side least-privilege role |
| Distributed rate limiting | In-process limiter only; multi-replica behavior not verified |

## 7. Verdict

Live infrastructure **Supabase**: REACHABLE and inspected read-only (historical window).
Application **local process**: VERIFIED against the live database.
Deployed production services: **REACHABLE / PARTIALLY VERIFIED** — live HTTP
probes succeeded, but the deployment still runs the pre-recovery build and no
authenticated or browser E2E was performed.
Recovery sprint code: **LOCALLY VERIFIED ONLY** — redeploy required before any
production claim can be made about these fixes.
