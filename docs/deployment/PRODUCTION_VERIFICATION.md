# Production Verification Record

Verification window: 2026-11-25T19:30Z–19:38Z (2026-11-26 01:30–01:38 UTC+06:00).
Repository state during verification: branch `main`, HEAD
`0cb3a0416962bddf2b290b69ecb6d158db9a8668` (plus the uncommitted changes made
by this sprint, listed in the final report).

This record distinguishes **live infrastructure evidence** from **local
verification**. No deployed Render or Vercel service was reachable, so no
production HTTP verification was possible.

## 1. Verified: Supabase (live, read-only)

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
| Render backend deployment | No connected Render tool, CLI or API token; no existing service identity available |
| Vercel frontend deployment | No connected Vercel tool, CLI or API token; no existing project identity available |
| Production backend URL | None exists in tracked files or accessible configuration |
| Production frontend URL | None exists in tracked files or accessible configuration |
| Browser-based E2E (login, navigation, console errors) | Requires a deployed site; no browser verification was performed |
| Authenticated API E2E | No authorized test token/account; none was created |
| Backup existence and restore drill | No `pg_dump`, no provider access, no backup artifact |
| Migration 0023/0024 applied to live DB | Blocked by unverified backup and missing authorization |
| RLS enforcement as non-superuser | Application config uses `postgres`; requires provider-side least-privilege role |
| Distributed rate limiting | In-process limiter only; multi-replica behavior not verified |

## 7. Verdict

Live infrastructure **Supabase**: REACHABLE and inspected read-only.
Application **local process**: VERIFIED against the live database.
Deployed production services: **NOT VERIFIED — DEPLOYMENT BLOCKED**.
