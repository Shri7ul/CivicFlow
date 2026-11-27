# CivicFlow — Local Three-Role End-to-End Validation, Autonomous Repair & Quality Loop

**Status:** completed locally, not pushed, not deployed.
**Scope:** isolated `127.0.0.1` environment only. No production data was read or written; no real citizen records, real credentials, or hosted database connections were used for these tests.
**Evidence:** real Chrome/Next.js/FastAPI interactions plus database state captured in gitignored `.cache/local_e2e/`. All screenshots in this report were captured from the running browser.

---

## 1. Environment and isolation

The repository's checked-in `backend/.env` points to a hosted Supabase project. It was treated as production-like and was **not** used for E2E writes. The original frontend environment file was preserved at the gitignored path `.cache/local_e2e/env.local.backup`.

| Component | Local value | Safety property |
| --- | --- | --- |
| Database | `sqlite:///.cache/local_e2e/civicflow.db` | Separate file, gitignored; migrated from scratch to head `0026_weather_intelligence`; 73 tables |
| Auth | `scripts/local_e2e/mock_gotrue.py` on `http://127.0.0.1:54321` | Local GoTrue/JWKS stand-in; synthetic in-memory accounts; real ES256 tokens signed by a gitignored local key |
| Backend | `http://127.0.0.1:8000` | `SUPABASE_JWKS_URL` pointed at the local mock; `WEATHER_PROVIDER=mock` |
| Frontend | `http://127.0.0.1:3100` (production build) | `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SUPABASE_URL` set to local services |
| Browser | Headless Chrome driven through CDP (`scripts/local_e2e/cdp.mjs`) | Real page renders, clicks, typing, cookies and screenshots; `Emulation.setDeviceMetricsOverride` for mobile |
| Weather | Mock provider | Advisory UI clearly shows "Simulated weather data (MOCK provider; not observed conditions)" |

Identity/access facts:

* Three principal accounts were used, all local-only:
  * `citizen.lifecycle@local.test` — CITIZEN, incident reporter.
  * `worker.test@local.test` — WORKER, created by applying through the UI and approved by Admin.
  * `admin.test@local.test` — ADMIN, seeded only in the isolated SQLite database.
* Additional synthetic signup checks used `signup.name2@local.test` and `payload.check@local.test`.
* Passwords were generated locally, exist only in gitignored harness artifacts, and are intentionally not reproduced here.
* No real Supabase project, hosted database, production user, or pilot boundary was involved.

---

## 2. Validation loop followed

The work repeated: inspect repository/DB state → exercise real UI → compare with API/DB evidence → identify defect → repair → add regression test → rebuild → retest → capture screenshot → re-score. No step was accepted only from a prior report.

Harness files added (both local-only, no credentials):

* `scripts/local_e2e/mock_gotrue.py` — GoTrue/JWKS mock; supports signup, password/refresh grants, user, logout and JWKS.
* `scripts/local_e2e/cdp.mjs` — CDP driver for navigation, form filling, clicking, viewport emulation, cookie handling and screenshots.

---

## 3. Citizen workflow — actual results

1. **Registration through UI** (`/signup`): form rendered, account created, session established, redirect to `/dashboard`. Screenshot: [01](screenshots/e2e/01-citizen-signup-form.png), [02](screenshots/e2e/02-citizen-after-signup.png).
2. **Login through UI**: local credentials accepted; role shown as `Citizen`; dashboard listed only the reporter's own incidents. Final state: `1 incident in this scope · 0 awaiting action`.
3. **Profile**: displayed profile id, active account status and role-appropriate navigation. Defect found and fixed: signup full name originally fell back to the email local part; after repair, a fresh UI signup displayed `Welcome, Synthetic Signup Name` and the DB profile held `Synthetic Signup Name` with role `CITIZEN` ([23](screenshots/e2e/23-signup-full-name-fix.png)).
4. **Incident creation** (`/incidents/new`): created "Standing rainwater beside a local road", severity `HIGH`, category `DRAINAGE`, synthetic Dhaka coordinates `23.812, 90.414`, status `OPEN`. Screenshots: [03](screenshots/e2e/03-citizen-incident-form.png), [04](screenshots/e2e/04-citizen-incident-created.png).
5. **Weather assessment**: the detail page rendered a persisted assessment with provider `mock`, observed values, forecast rows, provenance and explicit non-causality wording. Screenshot: [05](screenshots/e2e/05-citizen-incident-weather.png).
6. **Tracking/history**: incident detail showed a full status history with actor and timestamp for every transition. Final view showed `Resolved` and `RESOLVED Nov 26, 2026, 9:35 PM`. Screenshots: [21](screenshots/e2e/21-citizen-final-dashboard.png), [22](screenshots/e2e/22-citizen-final-incident-detail.png), mobile [26](screenshots/e2e/26-citizen-dashboard-mobile-390.png), [27](screenshots/e2e/27-citizen-resolved-incident-mobile-390.png).
7. **Security**: cannot open `/admin` or `/worker` — both redirected to `/dashboard`. Cannot list or create assignments, review applications, verify completions, or change roles. Reading another reporter's incident returned `404 incident_not_found`.

---

## 4. Worker workflow — actual results

1. **Application through the real workflow** (`/workforce/apply`): submitted `Drainage, Roads`, service area `Local test ward B`. Screenshots: [06](screenshots/e2e/06-worker-application-form.png), [07](screenshots/e2e/07-worker-application-submitted.png).
2. **Admin approval**: application moved `PENDING → APPROVED`, worker profile became `ACTIVE`, role changed to `WORKER`, and a `worker_application_approved` notice was created. The worker then logged in through the UI and saw `Field worker` navigation and an empty active-assignment list ([14](screenshots/e2e/14-worker-dashboard.png)).
3. **Assignment**: after Admin assigned the incident, the worker saw `Active assignments (1)`, opened the assignment and clicked **Accept**. `OFFERED → ACCEPTED` persisted in `incident_assignment_events` and `workforce_events` ([15](screenshots/e2e/15-worker-assignment-accepted.png)).
4. **Start work**: entered a synthetic work note and clicked **Start work**. Status `ACCEPTED → IN_PROGRESS`; UI exposed **Update progress** and **Submit completion** ([16](screenshots/e2e/16-worker-work-started.png)).
5. **Progress**: clicked **Update progress** with a 50% note; DB recorded `work_progress_updated`, `new_state = 50%` with the note. Screenshot: [17](screenshots/e2e/17-worker-progress-50pct.png).
6. **Completion**: submitted a synthetic completion note. Assignment became `COMPLETION_SUBMITTED`, `completed_at` was set, and it moved to **Work History** as `Awaiting verification`. The UI explicitly states completion does not resolve the incident by itself. Screenshot: [18](screenshots/e2e/18-worker-completion-submitted.png).
7. **Security**: cannot open `/admin` (redirected to `/worker`); `GET /api/v1/workforce/admin/overview`, `GET /api/v1/workforce/applications`, `POST /workforce/assignments`, `POST /workforce/assignments/{id}/verify`, application review and `PATCH /admin/profiles/{id}/role` all returned `403 insufficient_role`. Mobile viewport: [28](screenshots/e2e/28-worker-mobile-390.png).

---

## 5. Admin workflow — actual results

1. **Login and dashboard**: overview rendered live API counts, including `AWAITING VERIFICATION 1`, `ACTIVE WORKERS 2`, `TOTAL INCIDENTS 2`.
2. **Application review**: reviewed the worker application through the UI; approval persisted as above. Screenshots: [08](screenshots/e2e/08-admin-application-review.png), [09](screenshots/e2e/09-admin-application-approved.png).
3. **Incident verification and assignment**: found a real gap — the previous UI had no path to verify a fresh incident or create the first assignment even though the APIs existed. After repair, the **Incident review** tab verified `OPEN → VERIFIED` and assigned the best candidate; incident became `ASSIGNED` and assignment `OFFERED`. Screenshots: [11](screenshots/e2e/11-admin-incident-review.png), [12](screenshots/e2e/12-admin-incident-verified.png), [13](screenshots/e2e/13-admin-assignment-created.png).
4. **Completion verification**: **Assignments** showed `Awaiting verification`; clicking **Verify completion** moved the assignment to `VERIFIED_COMPLETED` (`verified_at` set) and automatically moved the incident to `RESOLVED` with `resolved_at` set. Screenshots: [19](screenshots/e2e/19-admin-awaiting-verification.png), [20](screenshots/e2e/20-admin-completion-verified.png).
5. **Notifications**: unread notices for application submitted/approved, assignment offered/accepted, work started and completion submitted were rendered on the overview. Clicking **Mark read** persisted `read_at` for one notice (1 row confirmed by SQL).
6. **Audit log**: **Audit log** rendered 14 events covering application, approval, assignment, acceptance, start, progress, completion, verification and resolution. Screenshot: [24](screenshots/e2e/24-admin-audit-log.png).
7. **Security**: admin-only endpoints returned `200` for the admin session while citizen/worker sessions returned `403`. Mobile viewport had `scrollWidth == clientWidth == 390` ([25](screenshots/e2e/25-admin-mobile-390.png)).

---

## 6. Complete incident lifecycle evidence

Incident `3a76003a-24e0-475e-b8ab-28c86b5189d4`, from `incident_status_events`:

| # | Transition | Actor | Timestamp (local test clock) |
| --- | --- | --- | --- |
| 1 | `null → OPEN` | citizen.lifecycle | 2026-11-26 21:22:55 |
| 2 | `OPEN → VERIFIED` | admin.test | 2026-11-26 21:30:28 |
| 3 | `VERIFIED → ASSIGNED` | admin.test | 2026-11-26 21:30:30 |
| 4 | `ASSIGNED → ACCEPTED` | worker.test | 2026-11-26 21:31:11 |
| 5 | `ACCEPTED → IN_PROGRESS` | worker.test | 2026-11-26 21:31:38 |
| 6 | `IN_PROGRESS → COMPLETION_SUBMITTED` | worker.test | 2026-11-26 21:34:49 |
| 7 | `COMPLETION_SUBMITTED → VERIFIED_COMPLETED` | admin.test | 2026-11-26 21:35:30 |
| 8 | `VERIFIED_COMPLETED → RESOLVED` | admin.test | 2026-11-26 21:35:30 |

Final DB state: `incidents.status = RESOLVED`, `resolved_at` set; assignment `status = VERIFIED_COMPLETED`, `completed_at` and `verified_at` set; 14 workforce audit events; 7+ workforce notifications. Citizen detail view reproduced all eight transitions in the browser history timeline.

---

## 7. Defect register, repairs and regression coverage

| ID | Severity | Symptom | Root cause | Fix / regression evidence |
| --- | --- | --- | --- | --- |
| E2E-01 | High | Admin could not verify a new incident or create the first assignment from the UI; completion verification API was unused | `admin-workspace.tsx` had no incident-review or verification controls | Added **Incident review**, initial assignment, and `Verify completion`/`Reject` actions; verified through real UI ([11](screenshots/e2e/11-admin-incident-review.png), [13](screenshots/e2e/13-admin-assignment-created.png), [20](screenshots/e2e/20-admin-completion-verified.png)) |
| E2E-02 | High | Frontend typecheck failed once workforce statuses were exercised: stale `IncidentStatus` missing `VERIFIED`, `ASSIGNED`, `ACCEPTED`, etc. | Frontend state machine lagged backend `ALLOWED_TRANSITIONS` | Updated `types/incidents.ts`, `lib/incidents.ts`, dashboard/detail maps and `incidents.test.ts`; `npm run typecheck` clean, 171 frontend tests pass |
| E2E-03 | High | Browser fetch to local Supabase failed with CSP violation | `next.config.ts` allowed only `https://*.supabase.co` / `wss://*.supabase.co` | Added `supabaseOrigins()` deriving HTTP/WS origins from `NEXT_PUBLIC_SUPABASE_URL` and included them in `connect-src` and `img-src`; local JWKS fetch then returned `200` |
| E2E-04 | Medium | Mock signup returned a message asking to check email instead of starting a session | GoTrue returns session fields at the top level for immediate sessions; mock nested them under `session` | Mock `/signup` now returns `_session(user)` directly; subsequent UI signup redirected to `/dashboard` |
| E2E-05 | Medium | Signup full name did not reach the profile; profile showed email local part | `loadOrProvisionProfile()` called `/auth/provision` without the Supabase `user_metadata.full_name` | `auth-provider.tsx` extracts `full_name`/`name` from session metadata; `lib/api/auth.ts` forwards it to provisioning. Regression test added to `auth-lifecycle.test.ts`; fresh UI signup verified in DB ([23](screenshots/e2e/23-signup-full-name-fix.png)) |
| E2E-06 | Low | Local mock user objects exposed `password_hash` | Credential hash stored inline in the GoTrue-shaped user payload | Moved hashes to a private in-memory `_PASSWORD_HASHES` map; verified on an isolated mock instance that `/auth/v1/user` keys contain no `password_hash` |
| E2E-07 | Info | Application notices appeared absent when querying the `notifications` table | Two distinct tables exist: generic `notifications` and workforce `workforce_notifications`; workflow notices use the latter | Confirmed 7+ `workforce_notifications` rows and admin UI rendering; no application defect |

No production data, production users, or hosted services were modified during any repair.

---

## 8. Security probes (actual HTTP status codes)

| Caller | Endpoint | Result |
| --- | --- | --- |
| citizen | `GET /api/v1/workforce/admin/overview` | `403 insufficient_role` |
| worker | `GET /api/v1/workforce/admin/overview` | `403 insufficient_role` |
| admin | `GET /api/v1/workforce/admin/overview` | `200` |
| citizen, worker | `GET /api/v1/workforce/applications` | `403 insufficient_role` |
| worker | `POST /api/v1/workforce/applications/{id}/review` | `403 insufficient_role` |
| citizen, worker | `POST /api/v1/workforce/assignments` | `403 insufficient_role` |
| citizen, worker | `POST /api/v1/workforce/assignments/{id}/verify` | `403 insufficient_role` |
| worker, citizen | `PATCH /api/v1/admin/profiles/{id}/role` | `403 insufficient_role` |
| citizen | `GET /api/v1/workforce/assignments` | `403 insufficient_role` |
| worker, admin | `GET /api/v1/workforce/assignments` | `200` |
| citizen | `GET /api/v1/incidents/{other reporter's incident}` | `404 incident_not_found` |
| citizen | `/admin`, `/worker` UI routes | redirected to `/dashboard` |
| worker | `/admin` UI route | redirected to `/worker` |

One admin role-change probe intentionally re-applied `CITIZEN` to an account that already had role `CITIZEN`; it returned `200` and caused no privilege change.

---

## 9. Verification commands and exact results

Executed from repository root unless noted.

```text
cd backend && .venv/Scripts/python.exe -m pytest -q --junitxml=../.cache/local_e2e/backend_tests.xml
  -> JUnit XML: tests=353, failures=0, errors=0, skipped=0, time=43.731s
  -> 2 known warnings: Starlette/httpx deprecation; SQLite reflection of expression index

cd backend && .venv/Scripts/python.exe -m alembic heads
  -> 0026_weather_intelligence (head)

cd frontend && npm run typecheck
  -> clean

cd frontend && npm run lint
  -> clean

cd frontend && npm test -- --reporter=dot
  -> 41 test files, 171 tests passed

cd frontend && npm run build
  -> succeeded; routes including /admin, /worker, /dashboard, /incidents/[id]

git diff --check
  -> clean (only CRLF normalization notices)

git check-ignore -v .cache/local_e2e/mock_key.pem .cache/local_e2e/civicflow.db frontend/.env.local backend/.env
  -> all ignored
```

Browser checks were run through `scripts/local_e2e/cdp.mjs` with per-role cookie files in `.cache/local_e2e/`. Mobile viewports reported `scrollWidth == clientWidth == 390` for admin overview, citizen dashboard, citizen resolved incident detail and worker workspace.

---

## 10. Screenshots

All 28 screenshots are in [`docs/hackathon/screenshots/e2e/`](screenshots/e2e/) and were captured from the running local application:

1. [Citizen signup form](screenshots/e2e/01-citizen-signup-form.png)
2. [Citizen after signup](screenshots/e2e/02-citizen-after-signup.png)
3. [Citizen incident form](screenshots/e2e/03-citizen-incident-form.png)
4. [Citizen incident created](screenshots/e2e/04-citizen-incident-created.png)
5. [Citizen incident weather panel](screenshots/e2e/05-citizen-incident-weather.png)
6. [Worker application form](screenshots/e2e/06-worker-application-form.png)
7. [Worker application submitted](screenshots/e2e/07-worker-application-submitted.png)
8. [Admin application review](screenshots/e2e/08-admin-application-review.png)
9. [Admin application approved](screenshots/e2e/09-admin-application-approved.png)
10. [Admin assignments](screenshots/e2e/10-admin-assignments.png)
11. [Admin incident review](screenshots/e2e/11-admin-incident-review.png)
12. [Admin incident verified](screenshots/e2e/12-admin-incident-verified.png)
13. [Admin assignment created](screenshots/e2e/13-admin-assignment-created.png)
14. [Worker dashboard](screenshots/e2e/14-worker-dashboard.png)
15. [Worker assignment accepted](screenshots/e2e/15-worker-assignment-accepted.png)
16. [Worker work started](screenshots/e2e/16-worker-work-started.png)
17. [Worker progress 50%](screenshots/e2e/17-worker-progress-50pct.png)
18. [Worker completion submitted](screenshots/e2e/18-worker-completion-submitted.png)
19. [Admin awaiting verification](screenshots/e2e/19-admin-awaiting-verification.png)
20. [Admin completion verified](screenshots/e2e/20-admin-completion-verified.png)
21. [Citizen final dashboard](screenshots/e2e/21-citizen-final-dashboard.png)
22. [Citizen final incident detail](screenshots/e2e/22-citizen-final-incident-detail.png)
23. [Signup full-name fix](screenshots/e2e/23-signup-full-name-fix.png)
24. [Admin audit log](screenshots/e2e/24-admin-audit-log.png)
25. [Admin mobile 390px](screenshots/e2e/25-admin-mobile-390.png)
26. [Citizen dashboard mobile 390px](screenshots/e2e/26-citizen-dashboard-mobile-390.png)
27. [Citizen resolved incident mobile 390px](screenshots/e2e/27-citizen-resolved-incident-mobile-390.png)
28. [Worker mobile 390px](screenshots/e2e/28-worker-mobile-390.png)

---

## 11. Re-score and remaining limitations

Self-assessment against the declared hackathon rubric (not an official judge score):

| Iteration | Self-score | Basis |
| --- | --- | --- |
| Pre-audit baseline recorded in the hackathon audit | 54/100 | Many claimed features lacked live evidence |
| After weather intelligence + audit repair | 94/100 | Feature-complete locally, but no full three-role lifecycle proof |
| First E2E pass | 86/100 | Real defects discovered: missing admin verification/assignment controls and stale lifecycle types |
| Final after repair and retest | **96/100** | Complete local lifecycle, role isolation, audit/notifications, responsive checks, full test suites green |

Remaining deductions are deliberate scope/safety choices, not hidden failures:

* E2E used the deterministic mock weather provider; the live Open-Meteo provider was verified in the earlier audit sprint but is not required for offline lifecycle proof.
* No deployment, push, production data activation, or pilot activation was performed in this sprint.
* No real municipal asset/feed integration or real citizen data was used; the UI explicitly labels local/synthetic provenance.
* The signup full-name fix was verified through the rebuilt UI and DB, but the isolated environment used a local GoTrue mock rather than hosted Supabase email confirmation.

No known blocking defects remain for the local three-role lifecycle.
