# CivicFlow — End-to-End Test Report

Date: 2026-11-26
Baseline: `main` at `bd926ac` (clean, synced). Final tree: recovery changes described in `docs/PROJECT_RECOVERY_REPORT.md`.

This report separates **locally verified** workflows from **production-verified** workflows. No claim of production E2E is made: no real production account, browser automation, platform redeploy, or production database write was used.

## 1. Executed checks (final state)

| Command | Result | Status |
| --- | --- | --- |
| `backend: python -m pytest` | **320 passed**, 2 pre-existing warnings | VERIFIED |
| `backend: python -m alembic heads` | single head `0024_phase14_pilot` | VERIFIED |
| `backend: pytest tests/test_recovery_contracts.py` | 4 passed | VERIFIED |
| `backend: pytest tests/test_provisioning_middleware.py` | 6 passed (baseline sprint) | VERIFIED |
| `frontend: npm run typecheck` | clean | VERIFIED |
| `frontend: npm run lint` | clean | VERIFIED |
| `frontend: npm test` | **36 files, 138 tests passed** | VERIFIED |
| `frontend: npm run build` | success, includes `/forgot-password` and `/update-password` | VERIFIED |
| Live `GET https://civic-flow-lilac.vercel.app` | 200, pre-recovery build served | VERIFIED (read-only) |
| Live `GET https://civicflow-8dol.onrender.com/api/v1/health` | 200 `healthy`, `environment: production` in this sprint; later probe hit Render Free cold-start interstitial | PARTIALLY VERIFIED |
| Live `GET /api/v1/health/dependencies` | 200, DB reachable, auth configured | VERIFIED (read-only) |
| Live `GET /docs` | 404 (production gating) | VERIFIED |

Pre-existing warnings: Starlette/httpx deprecation; SQLite expression-index reflection warning. Both are unrelated to this sprint.

## 2. Workflow verification matrix

| Workflow | Description | Local evidence | Production evidence | Status |
| --- | --- | --- | --- | --- |
| **A — Citizen** | Register → verify → login → provision → dashboard → create incident → view → logout | Supabase SSR integration + JWT/provisioning tests; `loadOrProvisionProfile` tests; backend incident tests; dashboard now loads real visibility-scoped incident data; coordinate helper tests | No real account or email was used | PARTIALLY VERIFIED (local only) |
| **B — Existing user** | Login → restore session → profile → protected pages → logout | `AuthProvider` session logic, `auth-lifecycle.test.ts`, `proxy.ts` cookie guard, role-aware `AuthGuard`/nav tests | No authenticated production session | PARTIALLY VERIFIED (local only) |
| **C — Authorization** | Citizen cannot reach worker/admin modules | Backend role-matrix tests; new `navigationForRole`/`canAccessPath` tests; `AuthGuard` redirect; validation run actions gated | No production request with a citizen token | VERIFIED locally |
| **D — Incident** | Create → persist → retrieve → ownership → status transition | Backend incident suite (7 tests) covers persistence, ownership, transitions; frontend coordinate parsing tests; fake default location removed | No production write | VERIFIED locally |
| **E — Geographic** | Map → real incident data → filter → select → detail | Real viewport API query in code; no fake markers; incident-map/risk-map code paths; map-header claim corrected; stale risk detail cleared | MapLibre glyph fetching not exercised in a browser | PARTIALLY VERIFIED |
| **F — Production integration** | Frontend/backend URLs, CORS, health, auth, callback, profile, DB | Config reviewed; smoke-test script available | Health/dependencies/frontend page probed read-only; deployed build is pre-recovery; CORS/auth/callback/profile not probed with credentials | PARTIALLY VERIFIED / BLOCKED |

## 3. Coverage added by this sprint

### Backend (`tests/test_recovery_contracts.py`)
1. `/risk/cells` declares a real 200 response schema.
2. Observation `submit` note is persisted in the append-only event history (payload no longer discarded).
3. Correlation engine `ValidationError` becomes a structured 422.
4. Decision engine `ValidationError` becomes a structured 422.

### Frontend
1. `src/config/security.test.ts` — geolocation allowlist and glyph `connect-src` required.
2. `src/lib/auth/routing.test.ts` — role-specific navigation visibility and path access.
3. `src/lib/location.test.ts` — empty coordinates rejected (no fabricated zero location), valid bounds accepted, invalid rejected.
4. `src/lib/auth/redirect.test.ts` — password-recovery callback preserves `next=/update-password`.

Existing coverage from prior sprints retained: JWT verification (11), auth API/RBAC (13), provisioning middleware (6), incidents (7), errors (6), risk engine (14), phase 12/14 controls (46), and frontend API/helper tests.

## 4. Explicitly NOT verified

- No browser E2E with a real Supabase account (registration email, PKCE exchange, session restore, password reset email delivery, logout) — no credentials or authorization were available.
- No production database query, migration, or write.
- No platform redeploy; the deployed frontend still shows pre-recovery copy ("Phase 13", "Phase 5", "35 tables"), proving the local fixes are not live.
- No Playwright/jsdom DOM tests; Vitest uses `environment: "node"`, so `AuthProvider`, `AuthNav`, `AuthGuard`, callback page, map components and incident UI states remain without component-level tests.
- No PostgreSQL/PostGIS integration tests (backend uses in-memory SQLite fixtures).
- No CORS preflight probe with an authenticated header from the production origin after the recovery changes.

## 5. Manual actions still required for production verification

1. Redeploy Render backend and Vercel frontend from the recovery commit.
2. Set/verify `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SITE_URL` on Vercel; `CORS_ORIGINS`, Supabase URL/JWKS/audience on Render; Supabase Site URL and redirect allowlist for `/auth/callback` and `/update-password`.
3. Use a real test account to run Workflows A, B and C in a browser, including password recovery.
4. Re-run `backend/scripts/production_smoke_test.py` against the redeployed backend.
5. Confirm the live home page no longer shows the stale phase/table copy.
