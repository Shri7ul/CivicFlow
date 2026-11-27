# CivicFlow — Final Product Recovery & Hackathon Submission Readiness

**Date:** 2026-11-27
**Scope:** local repairs, full three-role E2E, deployment probes, final screenshot evidence.
**Honesty rule:** every "verified" statement below was observed in a running browser/API or in test output. Anything that could not be verified is listed under blockers/limitations.

---

## 1. What was broken and why

| Reported symptom | Actual root cause | Evidence |
| --- | --- | --- |
| Users cannot find the Admin dashboard | Login always navigated to `/dashboard`; an ADMIN was then bounced to `/admin` by the route guard. The landing header's "Workspace" link was hardcoded to `/dashboard`, nav items used terse labels, and Admin had no active-state clarity. | `frontend/src/components/auth/auth-form.tsx`, `auth-nav.tsx`, `lib/auth/routing.ts`; `routing.test.ts` previously asserted Admin could not reach `/risk`. |
| `/risk` shows "You do not have permission to perform this action." | `getRiskDataQuality()` (staff-only, `require_worker`) was fetched inside the same `Promise.all` as the all-role config/cells/summary calls; one 403 blanked the whole page. Separately, `navigationForRole("ADMIN")` excluded `/risk`, so the guard redirected Admins away from Risk Intelligence. | `backend/app/api/v1/endpoints/risk.py:704` uses `require_worker`; `risk-map.tsx` loaded it in `Promise.all`; `routing.ts` admin list omitted `/risk`. |
| Citizen dashboard/navigation unclear | Citizen nav existed but labels were terse; the dashboard had no in-app notification inbox and no role-specific landing link from the public header. | `auth-nav.tsx`, `dashboard-view.tsx`. |
| Incident form "loses state"/appears to reload | The current form had no draft persistence, and both map components used `window.location.reload()` for the map retry button. When OSM tiles failed in the deployed build, clicking retry reloaded the whole page and discarded form input. | `incident-map.tsx` and `risk-map.tsx` previously called `window.location.reload()`; `report-incident-form.tsx` had no persistence layer. |
| OSM tiles fail | Single upstream tile host with no fallback; incident map had no tile-aware error handler; risk map treated any tile error as a fatal overlay and offered a full reload. | `lib/map.ts` OSM-only source; map error handlers. |
| Weather panel shows "Unable to reach the CivicFlow API" | That exact string is produced only by a failed browser `fetch`, not by the weather provider. Likely causes are a missing/stale `NEXT_PUBLIC_API_BASE_URL` build-time value, CSP misconfiguration for a self-hosted API, CORS, or backend cold start. Provider failures are returned as HTTP 200 with `status=STALE/ERROR`, so they never produce this message. | `frontend/src/lib/api/client.ts`; `backend/app/weather/service.py`, `errors.py`. |
| ML invisible / unclear | There is no trained model. Risk is a deterministic weighted engine; the frontend only printed a version/hash in a collapsed details block and never used the governance endpoints, so judges could not see inputs, output, confidence, timestamp or limitations. | `backend/app/risk/scoring.py`, `config.py`, `serialization.py`; no model artifacts or ML libraries in requirements. |
| Pages look disconnected | Each page independently composes `SiteHeader + AuthGuard + SiteFooter`; there is no shared app shell. This did not block functionality but weakened visual coherence. | `frontend/src/app/layout.tsx`, individual pages. |

A broader deployment drift was already documented in `docs/deployment/PRODUCTION_VERIFICATION.md` and `docs/PROJECT_RECOVERY_REPORT.md`: the live Vercel build had been serving pre-recovery code because no redeploy was performed. This sprint's push to `main` is intended to trigger the Vercel auto-deployment; live verification status is recorded in §8.

---

## 2. What was implemented / repaired

### Navigation and dashboards
- `lib/auth/routing.ts`: Admin can now reach `/risk` and `/incidents`; Worker can reach `/risk` and `/incidents`; all role allow-lists remain least-privilege (no Admin nav for Citizen/Worker, no Worker nav for Citizen).
- `components/auth/auth-nav.tsx`: explicit role labels, clear item names ("Dashboard", "My incidents", "Risk intelligence", "Incident review", "Worker desk", "Admin operations"), active `aria-current="page"` state, and a role-aware "Workspace" link on the public header.
- `components/auth/auth-form.tsx`: waits for the authoritative DB profile before redirecting; Admin lands on `/admin`, Worker on `/worker`, Citizen on `/dashboard`. Removed the double redirect that caused the bounce.
- `app/dashboard/dashboard-view.tsx`: added a real notifications inbox using `/api/v1/workforce/notifications` with mark-read, so Citizens can see status notices without an undocumented URL.

### Risk and ML visibility
- `components/map/risk-map.tsx`: the staff-only data-quality call is now independent and non-fatal; the main risk map and score summary render for all authorized roles even if that adjunct call is denied.
- `components/intelligence/risk-intelligence-panel.tsx`: new judge-facing panel showing engine/version, config hash, last inference time, execution location, input feature weights, current highest-score cell with score/category/confidence/incident count, and limitations. It explicitly labels the system **"Deterministic rules · not a trained ML model"**.
- No hardcoded scores: all values come from `/risk/config`, `/risk/cells?format=geojson` and `/risk/summary`.

### Incident form and state
- `lib/incident-draft.ts` + `app/incidents/new/report-incident-form.tsx`: all fields persist in `sessionStorage` per tab and are restored after tab changes, map interaction, remount or accidental navigation; the draft is cleared only after successful submission. Storage failures cannot block reporting.
- Removed map retry buttons that called `window.location.reload()`; retries now use `map.resize()` and `map.triggerRepaint()` only.

### Weather
- `components/weather/weather-impact-panel.tsx`: network/timeout failures now show a non-blocking, actionable message ("Weather context is temporarily unavailable... use Retry to reload only this panel"), 403 is reported as a role restriction, and 404 as "not generated yet". The existing targeted retry remains; no automatic page reload.

### Map
- `lib/map.ts`: added a lazy CARTO/OSM-attributed fallback tile source, `isTileLoadError()` and `installRasterTileFallback()`. On the first tile failure the raster source swaps once to the fallback; no loop, no prefetch, no reload.
- `next.config.ts`: CSP now permits the OSM and CARTO tile hosts in both `img-src` and `connect-src`, in addition to the API origin, Supabase origins and glyph host.
- Both incident and risk maps ignore tile errors in their fatal-error overlay so the fallback can recover the map; attribution includes both OSM and CARTO.

---

## 3. Actual ML implementation and inference path

- There is **no trained statistical model** in the repository: no serialized model artifacts and no training/inference ML libraries in `backend/requirements.txt`.
- Risk is computed by a deterministic weighted rules engine in `backend/app/risk/scoring.py`, configured by `backend/app/risk/config.py`. Inputs include incident counts/activity, category and severity weights, H3 spatial aggregation, infrastructure exposure, recency half-life and history coverage.
- Inference runs synchronously inside the API worker when `/api/v1/risk/cells`, `/risk/summary`, `/risk/cells/{id}` or `/risk/trends` is called. The UI now exposes the actual `model_version`, `config_hash`, `generated_at`, factor weights, confidence labels, factor contributions and limitations returned by those endpoints.
- The governance model registry is a configuration snapshot, not trained weights; the project does not claim otherwise.
- Weather is a separate advisory external-API component and never changes a risk score or incident severity automatically.

---

## 4. Actual weather implementation

- Provider abstraction with Open-Meteo live provider and a mock provider (`backend/app/weather/provider.py`); service cache with 30-minute TTL, stale-while-error and explicit `OK/STALE/ERROR/DISABLED` states (`backend/app/weather/service.py`, `errors.py`).
- GET `/api/v1/weather/incidents/{id}/assessment` is available to active users with scope filtering; POST `/refresh` and GET `/config` are Admin-only.
- Provider failures return HTTP 200 with a stable status rather than a connectivity error; the UI renders freshness, provenance, observed/forecast values and limitations.
- In the final E2E, blocking the assessment request produced a non-blocking warning with a targeted retry while the incident detail remained fully usable. Live Open-Meteo was verified in the earlier audit sprint, not in this sprint's deployed environment.

---

## 5. Test results (actual)

```text
cd backend && .venv/Scripts/python.exe -m pytest -q --junitxml=.../backend_final.xml
  -> 353 tests, 0 failures, 0 errors

cd frontend && npm run typecheck   -> clean
cd frontend && npm run lint        -> clean
cd frontend && npm test            -> 42 test files, 175 tests passed
cd frontend && npm run build       -> succeeded

cd backend && .venv/Scripts/python.exe -m alembic heads
  -> 0026_weather_intelligence (head)
```

New regression coverage:
- `frontend/src/lib/auth/routing.test.ts` — role landing paths and Admin/Worker access to Risk Intelligence.
- `frontend/src/lib/incident-draft.test.ts` — draft round-trip, malformed payload handling, selective clear.
- Existing `frontend/src/lib/api/auth-lifecycle.test.ts` — full-name provisioning.
- Existing backend RBAC/weather/risk tests continued to pass.

---

## 6. End-to-end results (real browser, isolated local environment)

Environment: SQLite `.cache/local_e2e/civicflow.db`, local GoTrue/JWKS mock on `127.0.0.1:54321`, backend on `8000`, frontend production build on `3100`, deterministic mock weather provider. No production accounts or data were used.

Observed in the final repaired build:

1. Citizen `/risk`: no permission error; "Intelligence & model transparency" and "Deterministic rules · not a trained ML model" visible; nav shows Dashboard / My incidents / Map / Risk intelligence / Apply / Application only.
2. Admin `/admin`: nav includes Risk intelligence; clicking it reaches `/risk` and renders the intelligence panel.
3. Incident form: after filling title, description and coordinates, navigating to `/incidents` and back restored every field; no full-page reload was triggered by a local interaction.
4. Weather failure: with the assessment request blocked, the detail page still showed the incident and `Resolved` status, displayed the non-blocking weather warning, exposed "Retry weather context", and stayed on the same URL.
5. Map failure: with OSM tile requests blocked, the map canvas still rendered; 24 OSM requests were attempted and 28 CARTO fallback requests were observed, with no page reload.
6. Full final lifecycle: new synthetic incident `19312e29-5009-4e0f-9619-7ec5cd85187a` went `OPEN → VERIFIED → ASSIGNED → ACCEPTED → IN_PROGRESS → COMPLETION_SUBMITTED → VERIFIED_COMPLETED → RESOLVED`; the citizen detail page showed the resolved status and complete history.
7. Security: prior role probes in `CIVICFLOW_LOCAL_E2E_ROLE_VALIDATION.md` remain valid — citizen/worker receive 403 on Admin APIs, citizen cannot read another reporter's incident, and unauthorized UI routes redirect to the role's own workspace.

Screenshot directory: `docs/hackathon/screenshots/final/` (28 real captures, including live landing, all three dashboards, Risk Intelligence, ML panel, map fallback, weather degradation, form state, lifecycle steps, audit log and mobile views).

---

## 7. Deployment verification

**Verified live:**
- `https://civic-flow-lilac.vercel.app/` and `/login` return HTTP 200; the landing page rendered in a real browser.
- `/risk` unauthenticated returns 307 to `/login?next=%2Frisk` — the optimistic route guard works.
- Live CSP permits the Render API origin and the configured Supabase origin.
- `https://civicflow-8dol.onrender.com/api/v1/health` returns HTTP 200.
- Live risk/weather endpoints return 401 without a token, and CORS returns `access-control-allow-origin: https://civic-flow-lilac.vercel.app`.

**Not verified live (exact blockers):**
- No Vercel or Render CLI is installed and no deployment credentials are present in the environment, so I could not trigger or inspect a deployment directly from this session.
- No production account or token was available, so authenticated live dashboards, the live Risk page, live weather and live ML panel could not be exercised. I did not create production accounts or alter real users.
- The live database migration head cannot be inspected without production DB credentials. Historical deployment docs recorded head `0022` with `0023`–`0026` pending; weather needs `0026` and workforce needs `0025`. This must be checked by an operator before relying on live weather/workforce.
- Therefore **authenticated deployed functionality is not claimed as verified**. The local production build and API are verified; public live surfaces and backend health/CORS are verified.

Deployment path: pushing to `main` is the available trigger for Vercel/Render auto-deployments. After the push, re-check the live bundle for the strings `Deterministic rules` and `Intelligence & model transparency` to confirm the new build is live; then repeat the authenticated flow with an authorized test account.

---

## 8. Rubric mapping (from the actual problem statement/rubric)

The rubric source and baseline criteria matrix are recorded in
`CIVICFLOW_HACKATHON_AUTONOMOUS_AUDIT.md`. The declared track is World Problem Solver; declared advanced challenges are `A02 — Intelligent Decisions & Optimization` and `A06 — External API & Fault Tolerance`.

| What judges need to see | Where it is now demonstrable |
| --- | --- |
| The civic problem and who uses it | Landing page, role-aware navigation, README submission block |
| Citizen reports an incident | `/incidents/new`, draft-preserving form, final demo screenshots 19–20 |
| System assesses/contextualizes risk | `/risk` map, summary cards, Risk Intelligence panel |
| What the ML system actually does | Intelligence & model transparency panel: deterministic engine, weights, confidence, generated-at, limitations; explicitly not a trained model |
| Weather contribution | Weather impact panel on incident detail, with provider/freshness/provenance and graceful degradation |
| Admin prioritises | Admin dashboard, Incident review, best-candidate assignment rationale |
| Workers execute | Worker desk, accept/start/progress/completion workflow |
| Completion verified | Admin Assignments → Verify completion; incident becomes Resolved |
| Measurable output | H3 risk cells, factor scores, confidence, audit events, status timeline, notifications |

No inflated numeric self-score is asserted here. The honest position is: local product and workflow are verified; authenticated live verification remains an operator-dependent blocker.

---

## 9. Remaining limitations

- No trained ML model: the intelligence layer is deterministic and labelled as such. Adding a trained model would require a real dataset, training pipeline and evaluation; none is fabricated here.
- Weather in the final E2E used the mock provider; live Open-Meteo was validated in the earlier audit sprint only.
- No real municipal feed or production dataset was used; local evidence is synthetic and labelled.
- The presentation video is still not published.
- Live authenticated verification and migration-head confirmation are blocked by missing deployment/database credentials.
