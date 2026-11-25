# CivicFlow — Project Recovery Report

Date: 2026-11-26
Baseline: `main` at `bd926ac262cb28e874f0fcdb6aef75ce7dee8279`, clean and synced with `origin/main`.

## 1. Overall verdict

**PARTIAL** — with clearly bounded scope.

The repository was not in the state the request described: both platforms are live, the API is coherent and well tested, and all automated checks were green at baseline (316 backend + 132 frontend tests). The real problems were product defects, missing features, contract defects and stale documentation. Those were addressed with targeted, evidence-backed changes. A **full visual redesign was not performed**; the shell, dashboard, navigation and design system received targeted corrections (real dashboard data, role-aware navigation and guard, focus states, skip link, accurate copy). I did not replace the architecture, activate the pilot, run migrations, write production data, or deploy.

## 2. Major defects found

1. Incident form submitted hard-coded Dhaka coordinates as a real location.
2. Geolocation blocked by `Permissions-Policy: geolocation=()`.
3. Map glyph requests blocked by CSP `connect-src`.
4. Navigation exposed staff-only modules to citizens; no role-aware guard.
5. Generic 401/403 responses had no dedicated handling or error boundary.
6. Password recovery did not exist.
7. `/risk/cells` had `response_model=None`.
8. Observation submission silently discarded its request body.
9. Validation correlation/decision engine errors surfaced as 500.
10. Stale phase/table counts and "Not started" claims in shipped UI and README.
11. Deployment docs claimed no live deployment despite verified live URLs.
12. Dashboard showed only profile data and static capability lists — no real metrics.

## 3. Root causes

- **Security headers added without checking dependent browser APIs** (items 2, 3).
- **Placeholder form state never replaced with an explicit-user-choice requirement** (item 1).
- **Backend authorization enforced, but frontend navigation mirrored no role model** (item 4).
- **Auth work focused on the profile lifecycle and stopped before generic API errors and recovery** (items 5, 6).
- **Endpoint annotations and handlers drifted from their schemas/services** (items 7, 8, 9).
- **Documentation accumulated point-in-time claims that were never reconciled with later deployments** (items 10, 11).

## 4. Backend changes

| File | Change |
| --- | --- |
| `app/api/v1/endpoints/risk.py` | `response_model=RiskCellsResponse | RiskGeoJSONResponse` instead of `None`. |
| `app/api/v1/endpoints/phase14.py` | Observation submit now forwards `payload.note` instead of `del payload`. |
| `app/phase14/observations.py` | `submit_observation` accepts `note` and records it on the append-only SUBMITTED event. |
| `app/api/v1/endpoints/validation.py` | Correlation and decision runs catch `ValidationError` and return structured 422. |
| `app/api/v1/endpoints/phase10.py` | Docstring corrected to match actual WORKER/ADMIN permissions (no authorization semantics changed). |
| `app/services/profiles.py` | Removed unreachable full-name guard. |
| `tests/test_recovery_contracts.py` | New: 4 regression tests for the above contracts. |

Status: **FIXED** (locally verified).

## 5. Frontend changes

| Area | Change |
| --- | --- |
| `next.config.ts` | `geolocation=(self)`; glyph origin added to `connect-src`. |
| `incidents/new/report-incident-form.tsx` + `lib/location.ts` | Empty coordinates required explicit location; shared `parseCoordinates`; no fabricated zero pin. |
| `components/map/location-picker.tsx` | No marker until a real location is chosen. |
| `lib/auth/routing.ts`, `auth-nav.tsx`, `auth-guard.tsx` | Role-aware navigation and UX redirect; backend remains authoritative. |
| `auth-provider.tsx` | 401 from any authenticated API/upload request signs out with a clear message. |
| `forgot-password`, `update-password`, `auth-form` | Complete password-recovery flow using config-driven redirect. |
| `dashboard-view.tsx` | Real visibility-scoped incident counts and recent incidents; role-aware quick actions; loading/error/empty states. |
| `auth-shell.tsx`, `globals.css`, `layout.tsx` | Single h1 per page, global focus-visible ring, skip link. |
| `app/page.tsx`, `config/app.ts` | Accurate current-phase copy; removed false "Not started" and "35 tables" claims. |
| `incident-map.tsx`, `risk-map.tsx`, `validation-dashboard.tsx` | Honest Dhaka label; stale detail cleared; run actions hidden from citizens. |
| Tests | New/updated: security headers, role navigation, coordinate parsing, recovery redirect (138 total). |

Status: **FIXED** for enumerated defects; **PARTIAL** for the broader "premium redesign" goal.

## 6. Authentication status

**PARTIALLY VERIFIED / FIXED (local).** Registration, login, PKCE callback, session restore, profile provisioning and logout were already implemented and covered by tests; this sprint added missing 401 handling and password recovery. No production account or email was used, so live verification remains **BLOCKED**.

## 7. RBAC status

**VERIFIED locally.** Three roles (CITIZEN/WORKER/ADMIN), backend enforcement on every endpoint, ownership checks, admin guards, and new frontend role-aware navigation/guard tests. Frontend hiding is UX only; backend is authoritative. Production browser verification remains unverified.

## 8. Incident workflow status

**VERIFIED locally.** Creation, persistence, visibility scoping, ownership edits and forward-only status transitions are covered by backend tests. The fabricated-location defect is fixed. No production incident was created.

## 9. Geographic workflow status

**PARTIALLY VERIFIED.** Real API-backed markers, no fake data, honest Dhaka research-only labelling, CSP glyph fix. MapLibre rendering and mobile behavior were not exercised in a browser.

## 10. Risk module status

**PARTIALLY VERIFIED.** Real H3 calculations and explainable factors exist; `/cells` contract fixed. Outputs remain research-oriented and require authoritative data. No score was fabricated.

## 11. Decision module status

**PARTIALLY VERIFIED.** Real bounded simulation with `execution_authorized=false`, `dispatch_performed=false`; no fake AI recommendations or dispatch.

## 12. Validation / pilot readiness status

**PARTIALLY VERIFIED / REQUIRES OPERATOR ACTION.** Real persisted experiments and honest empty states; engine errors now structured; no fake readiness scores. Pilot remains **NOT READY / INACTIVE**; no model activated.

## 13. Design changes

Targeted rather than complete: real-data role-aware dashboard, role-aware navigation, global focus states, skip link, consistent dark/emerald system retained, misleading copy removed. A full visual redesign of every module was **not** attempted, to avoid breaking working workflows without evidence.

## 14. Security changes

No security control was weakened. Geolocation was enabled narrowly (`self`) and glyph fetching allowlisted explicitly. Auth 401 handling signs out rather than bypassing. No role is accepted from browser payloads. No secrets, service-role keys, migrations, RLS changes or production writes were made. Rate limiting remains in-process and proxy-keyed — documented as an operator limitation rather than changed to a spoofable header trust model.

## 15. Test results

- Backend: **320 passed**, 2 warnings; single Alembic head `0024_phase14_pilot`.
- Frontend: **36 files / 138 tests passed**; typecheck clean; lint clean; production build success.
- Details: `docs/testing/END_TO_END_TEST_REPORT.md`.

## 16. Production verification results

- Frontend `https://civic-flow-lilac.vercel.app`: **200**, but serves the pre-recovery build (stale phase copy) — proves fixes are not live.
- Backend `https://civicflow-8dol.onrender.com/api/v1/health`: **200** observed in this sprint; a later probe hit Render Free's cold-start interstitial.
- `/api/v1/health/dependencies`: **200**, DB reachable, auth configured.
- `/docs`: **404** (correct production gating).
- No authenticated or browser E2E in production.

## 17. Remaining blockers

1. **Deployment of recovery code** — no Render/Vercel CLI/connector/token; live services still run the old build.
2. **Real-account browser E2E** — no credentials; no user created.
3. **Supabase dashboard config** — Site URL/redirect allowlist and CORS must be confirmed by operator.
4. **Migration 0023/0024** — pending per existing docs; no backup/restore verification and no authorization.
5. **RLS least-privilege role** — app reportedly uses `postgres`; provider-side change.
6. **Distributed rate limiting / trusted proxy** — in-process limiter; needs operator decision.
7. **Component/DOM tests and Postgres integration tests** — not added; require new dev dependencies and infrastructure.
8. **Full visual redesign** — not completed.

## 18. Commit hashes

| Commit | Subject |
| --- | --- |
| `ce3f4ee` | `docs(audit): add full project audit and verified baseline` |
| `014441f` | `fix(api): honour declared request and response contracts` |
| `240b7d4` | `fix(frontend): restore broken workflows and complete password recovery` |
| `8f5af0b` | `docs(recovery): reconcile live deployment state and record results` |
| final commit | `docs(recovery): record final commit hashes and push status` |

## 19. Push status

`origin/main` — pushed only after all checks passed. The final HEAD hash and
push result are reported in the final chat message. The live deployment still
serves the pre-recovery build until an operator redeploys.

## 20. Exact manual actions required

1. Redeploy Render from `main` (backend contract fixes, geolocation-independent backend changes).
2. Redeploy Vercel from `main` with `NEXT_PUBLIC_API_BASE_URL=https://civicflow-8dol.onrender.com` and `NEXT_PUBLIC_SITE_URL=https://civic-flow-lilac.vercel.app`.
3. In Supabase Auth, allow `https://civic-flow-lilac.vercel.app/auth/callback` and `https://civic-flow-lilac.vercel.app/update-password` redirects.
4. Verify Render `CORS_ORIGINS` includes the Vercel origin; verify Supabase URL/JWKS/audience.
5. With a real test account: register → verify email → login → provision → dashboard metrics → create incident with explicit location → view incident → forgot password → reset → logout.
6. Re-run `backend/scripts/production_smoke_test.py` and confirm the live home page no longer shows stale phase counts.
7. Decide separately, with backup/restore drill and explicit authorization, whether to apply migrations `0023`/`0024`.
