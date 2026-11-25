# CivicFlow — Full Project Audit

Date: 2026-11-26
Baseline: `main` at `bd926ac262cb28e874f0fcdb6aef75ce7dee8279`, clean, synced with `origin/main`.
Method: direct source inspection by four parallel read-only audit passes (backend, frontend, deployment/docs, tests), followed by manual verification of every high-impact finding by the sprint lead. Test commands were executed; production HTTP probes were read-only GETs. No files were changed before this report was written.

Status legend: **VERIFIED WORKING** (asserted by passing tests or live evidence) · **PARTIALLY WORKING** · **BROKEN** · **NOT IMPLEMENTED** · **BLOCKED BY EXTERNAL CONFIGURATION** · **REQUIRES REAL DATA** · **REQUIRES OPERATOR ACTION**. Classifications are based on implementation + evidence, never on file existence.

---

## 1. Executive summary

The application is **materially better than the user's opening assessment suggests**: both platforms are live and reachable, the backend exposes a coherent, well-tested API surface, and 448 automated tests pass. However, there are real product defects that make parts of the experience incoherent or misleading:

- Two browser features are actively broken by security headers (`geolocation`, map glyphs).
- The incident form submits hard-coded Dhaka coordinates when the user never placed a pin (fake location presented as a real report).
- Navigation shows staff-only modules to citizens, who then receive 403s with no dedicated UI.
- Password recovery does not exist.
- Generic API errors are not classified into unauthorized/forbidden/offline states.
- Several shipped and documented phase/table counts contradict reality.
- Several deployment documents still claim "deployment blocked / no URL", contradicted by live 200 responses.

Overall verdict: **PARTIALLY WORKING** with **BROKEN** and **NOT IMPLEMENTED** items identified below. The sprint proceeds with targeted, evidence-backed repairs rather than an architecture rewrite.

---

## 2. Live deployment reality (verified this sprint)

| Probe | Result | Status |
| --- | --- | --- |
| `GET https://civicflow-8dol.onrender.com/api/v1/health` | `200`, `{"status":"healthy","environment":"production","version":"v1"}`; HSTS/CSP/request-id present | VERIFIED WORKING |
| `GET /api/v1/health/dependencies` | `200`, `database: reachable`, `auth_verification_configured: true`, build `0.11.0` | VERIFIED WORKING |
| `GET /docs` | `404` (production gating active) | VERIFIED WORKING |
| `GET https://civic-flow-lilac.vercel.app` | `200`, rendered page; CSP `connect-src` includes the Render origin | VERIFIED WORKING |

This means documents claiming no deployment URL are stale, not current facts.

---

## 3. Feature classification

### 3.1 Authentication and identity

| Feature | Status | Evidence |
| --- | --- | --- |
| Login (`signInWithPassword`) | VERIFIED WORKING | `frontend/src/app/login/page.tsx`, `auth-form.tsx`; Supabase SSR |
| Registration (`signUp`, PKCE confirm) | VERIFIED WORKING | `frontend/src/app/signup/page.tsx` |
| Email verification callback + code exchange | PARTIALLY WORKING | `frontend/src/app/auth/callback/page.tsx:26-49` real exchange; no component tests for invalid/expired/missing-code branches (`lib/auth/callback.test.ts` covers parsing only) |
| Verification redirect origin | PARTIALLY WORKING | `lib/auth/redirect.ts` prefers `NEXT_PUBLIC_SITE_URL`; requires operator to set it in Vercel and allowlist the callback in Supabase |
| Session restoration + token refresh | VERIFIED WORKING (code) | `auth-provider.tsx:127-164`, `TOKEN_REFRESHED` updates `sessionRef` |
| Profile provisioning (403 `profile_required` → `POST /provision`) | VERIFIED WORKING | `lib/api/auth.ts:19-32`, `auth-lifecycle.test.ts` (8), backend `test_provisioning_middleware.py` (6) |
| Provisioning idempotency / CITIZEN-only / no role in browser payload | VERIFIED WORKING | `services/profiles.py:31-62`, `test_auth_api.py`, `auth-lifecycle.test.ts:157-168` |
| Logout | PARTIALLY WORKING | `auth-nav.tsx:77-93` has correct ordering; no automated coverage |
| Password recovery / reset | **NOT IMPLEMENTED** | No `resetPasswordForEmail`, reset page, reset callback handling, "Forgot password" link, or backend reset endpoint anywhere in source |
| Generic API 401/403 handling | **BROKEN** | `auth-provider.tsx:216-226` `apiRequest` attaches a token but never inspects the response; no `error.tsx`/`not-found.tsx` or error boundary exists in `frontend/src/app` |
| Backend JWT verification | VERIFIED WORKING | `backend/app/auth/jwt.py:69-141`, strict asymmetric-only algorithms, `test_auth_jwt.py` (11) |
| Route protection | PARTIALLY WORKING | `frontend/src/proxy.ts:15-40` checks auth cookie; `auth-guard.tsx` handles unauthenticated/unconfigured/error; client-side authorization not implemented |

### 3.2 Authorization / RBAC

| Feature | Status | Evidence |
| --- | --- | --- |
| Backend roles CITIZEN / WORKER / ADMIN | VERIFIED WORKING | `models/enums.py:8-11`, `auth/dependencies.py:107-132`, parametrized role-matrix tests |
| Backend route enforcement | VERIFIED WORKING | Every endpoint in `api/v1/endpoints/` carries a dependency; `test_auth_api.py:271-293` |
| Ownership checks (incidents) | VERIFIED WORKING | `services/incidents.py:96-105`, `:309-311` |
| Admin self-promotion / last-admin guards | VERIFIED WORKING | `services/profiles.py:128-160` |
| Frontend route hiding / role-aware navigation | **BROKEN** | `components/auth/auth-nav.tsx:24-95` renders every module link to every authenticated user |
| Service-role credentials | VERIFIED WORKING (backend only) | `services/storage.py:35` uses `SecretStr`; frontend config rejects `service_role` keys (`lib/supabase/config.ts:26-33`) |
| Supabase RLS | BLOCKED BY EXTERNAL CONFIGURATION | Policies exist in migrations, but docs report app role `postgres`, which bypasses RLS; least-privilege role requires provider-side action |

### 3.3 Incident workflow

| Feature | Status | Evidence |
| --- | --- | --- |
| Create incident + persistence | VERIFIED WORKING | `services/incidents.py:135-170`, `test_incidents_api.py` |
| Categories, validation, ownership, IDs, timestamps | VERIFIED WORKING | Same; WKT point validation and reporter-only edits while OPEN |
| Status transitions with event history | VERIFIED WORKING | `ALLOWED_TRANSITIONS` `:42-50`, department requirement `:268-273` |
| Frontend list/detail/filters/states | VERIFIED WORKING | `incidents-view.tsx`, `incident-detail-view.tsx` use real APIs |
| Location selection in "new incident" form | **BROKEN** | `report-incident-form.tsx:34-35,87-88` defaults to Dhaka coordinates and submits them; `next.config.ts:47` also blocks geolocation via Permissions-Policy |
| Evidence upload / signed URL | PARTIALLY WORKING | Requires Supabase Storage + service-role; no live proof of upload |

### 3.4 Map and geography

| Feature | Status | Evidence |
| --- | --- | --- |
| Real incident markers (no fake data) | VERIFIED WORKING | `lib/map.ts:82-89`, viewport-bounded API query `incident-map.tsx:387` |
| Map text labels / glyphs | **BROKEN** | `lib/map.ts:22` fetches glyphs from `fonts.openmaptiles.org`, but CSP `connect-src` (`next.config.ts:21-26,33`) omits that origin; `font-src` does not govern glyph fetches |
| "Use my location" on map | **BROKEN** | `incident-map.tsx:465-498` uses geolocation blocked by `next.config.ts:47` |
| Risk GeoJSON map | PARTIALLY WORKING | Real API data (`risk-map.tsx:508-512`); stale `detail` state when selection changes (`:568-594`) |
| Geographic validation / contexts / H3 | PARTIALLY WORKING | `geo/contexts.py` registry-backed; Dhaka marked BLOCKED and `researchOnly: true`; H3 engine real but `REQUIRES REAL DATA` |
| Geographic labeling | PARTIALLY WORKING | Map header says "live reports around Dhaka" (`incident-map.tsx:521-522`) while geography config marks Dhaka research-only |

### 3.5 Risk, decisions, operations, validation, pilot

| Feature | Status | Evidence |
| --- | --- | --- |
| Risk H3 engine + scoring | PARTIALLY WORKING | Real calculations, 14 engine tests; meaningful output `REQUIRES REAL DATA` |
| Risk `/cells` API contract | BROKEN (contract) | `risk.py:204-207` `response_model=None` on a union return type → no OpenAPI schema, no response validation |
| Decision simulation | PARTIALLY WORKING | Real bounded simulation; explicitly `execution_authorized=False`, `dispatch_performed=False` (`decisions.py:853-855`) — planning only, correctly labelled |
| Operations dashboard | VERIFIED WORKING | Real DB-backed alerts/quality/reviews; ADMIN mutations gated in UI (`operations-dashboard.tsx:332,393,411`) |
| Validation experiments/reports | PARTIALLY WORKING | Real persisted data, honest empty states; admin "Run" actions exposed to all roles in UI (`validation-dashboard.tsx:404-442`); correlation/decision endpoints leak engine errors as 500 (`validation.py:278-299`) |
| Pilot / Phase 14 readiness | PARTIALLY WORKING | Full state machines, activation gated, separation of duties; `REQUIRES OPERATOR ACTION` for evidence/attestations |
| Phase 14 observation submission | BROKEN (contract) | `phase14.py:221-234` accepts `ObservationSubmit` then `del payload` — client input silently discarded |
| Phase 10 governance policy | PARTIALLY WORKING | Docstring says mutating routes ADMIN-only (`phase10.py:3-4`), but `POST /reviews`, review decisions and correlation reviews use `require_worker` (`:394-399`, `:451-457`, `:555-561`) |

### 3.6 Frontend quality, UX, design

| Feature | Status | Evidence |
| --- | --- | --- |
| Cross-module design system | PARTIALLY WORKING | `globals.css` dark/emerald system is consistent; `geography-panel.tsx` uses a divergent palette; reduced-motion handled |
| Loading/empty/error states | PARTIALLY WORKING | Present on most data views; absent for unauthorized/forbidden/offline and for generic 401/403 |
| Accessibility | PARTIALLY WORKING | 55 aria-labels, role=status/alert; only 2 `focus-visible` classes, no skip link, 10+ focusable links before `<main>` |
| Mobile responsiveness | PARTIALLY WORKING | Responsive classes present; navigation rail not adapted into a proper mobile drawer |
| Navigation links | VERIFIED WORKING (no dead links) | No `href="#"`; all targets exist — but visibility is not role-aware (see RBAC) |
| Phase/table-count messaging | BROKEN (content) | Shipped UI says "Phase 13"/"35 tables" (`config/app.ts:7-8`, `app/page.tsx:122`) while README and backend describe Phase 14 and 53–57 tables; "Not started" claims contradict existing pages (`app/page.tsx:95-100`) |
| Frontend tests | VERIFIED WORKING (limited scope) | 132 pass, but `AuthProvider`, `AuthNav`, `AuthGuard`, callback page, `proxy.ts`, map and incident UI have no automated coverage; Vitest uses `environment: "node"` so no DOM interaction testing |

### 3.7 Backend infrastructure

| Feature | Status | Evidence |
| --- | --- | --- |
| Consistent error envelope | VERIFIED WORKING | `core/exceptions.py:49-64`, `test_errors.py` |
| Middleware request IDs / security headers | VERIFIED WORKING | `core/middleware.py`, `test_phase13_hardening.py` |
| Health / readiness / dependencies | VERIFIED WORKING | `health.py` only `SELECT 1` (`db/health.py:48-51`), no writes; live 200 |
| Rate limiting | PARTIALLY WORKING | In-process, keyed on socket peer (`middleware.py:99-100`): behind Render proxy all users share one quota; single-instance only — needs edge enforcement |
| Alembic chain | PARTIALLY WORKING | 24 files, single head `0024_phase14_pilot`; `0015_ingested_record_provenance.py:16` declares revision `0015_ingested_provenance` (filename mismatch, chain still valid) |
| Live DB migration status | REQUIRES OPERATOR ACTION | Docs report live head `0022`; `0023`/`0024` pending; no verified backup/restore, no authorization to migrate |
| Dependency inventory | VERIFIED WORKING | Backend pyproject/requirements mirror exactly; frontend lockfile consistent |
| CI gates | PARTIALLY WORKING | `.github/workflows/verify.yml` runs pytest, single-head check, typecheck, lint, Vitest, build, secret scan; no dependency audit, no `alembic check`, no browser E2E, no Postgres integration |

### 3.8 Documentation

| Feature | Status | Evidence |
| --- | --- | --- |
| Deployment docs accuracy | **STALE / INCORRECT** | `PRODUCTION_DEPLOYMENT_AUDIT.md`, `PRODUCTION_DEPLOYMENT_REPORT.md`, `PRODUCTION_VERIFICATION.md`, `PRODUCTION_RUNBOOK.md`, `RENDER_WEB_SERVICE_DEPLOYMENT.md` claim "blocked / no URL / not deployed" despite live 200s |
| Point-in-time auth docs | PARTIALLY VERIFIED | `PRODUCTION_AUTH_INTEGRATION_FIX.md` observed `environment: development` and `/docs` 200; live now production and 404 — remediation remains relevant |
| Phase counts | STALE / INCORRECT | README says 14 vs 53 vs 57 tables in three places; `PROGRESS.md` test counts are snapshots |

---

## 4. Highest-impact defects, ranked

1. **Incident form submits fabricated location** — `report-incident-form.tsx:34-35,87-88` (fake data presented as real).
2. **Geolocation blocked by Permissions-Policy** — `next.config.ts:47` vs `report-incident-form.tsx:41-64` and `incident-map.tsx:465-498`.
3. **Map glyphs blocked by CSP** — `lib/map.ts:22` vs `next.config.ts:21-26,33`.
4. **Role-unaware navigation** — `auth-nav.tsx:24-95` sends citizens into 403-only modules.
5. **No generic 401/403/error boundary handling** — `auth-provider.tsx:216-226`; no `error.tsx`.
6. **Password recovery missing entirely** — no source implementation.
7. **Backend contract defects** — `/risk/cells` `response_model=None` (`risk.py:204-207`), discarded observation payload (`phase14.py:229`), validation errors as 500 (`validation.py:278-299`).
8. **Stale deployment documentation** — contradicts verified live state.
9. **Misleading phase/table counts in shipped UI and README**.
10. **Rate limiter proxy aggregation** — `middleware.py:99-100` (documented as operator limitation; changing trust semantics without an explicit proxy configuration would weaken security, so no code change is proposed here).

---

## 5. What this audit does NOT claim

- No production browser E2E was executed; live verification was read-only HTTP GETs only.
- No production database state was queried; migration status comes from existing docs.
- No password reset email was sent; the feature does not exist yet.
- No claim is made that risk scores are validated predictive outputs — they are research/planning outputs requiring real data.
