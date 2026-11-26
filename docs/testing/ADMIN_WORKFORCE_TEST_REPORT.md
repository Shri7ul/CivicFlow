# Admin & Workforce Test Report

Date: 2026-11-26. Baseline: working tree on `main` at `c11d1dd` plus this sprint's
uncommitted changes. All results below were produced by running the commands in
this repository, not inferred from earlier reports.

## 1. Environment

- Backend: Python 3 (project `.venv`), pytest 9.2.0, in-memory SQLite for service
  and API tests (`tests/conftest.py`), Alembic for migration graph validation.
- Frontend: Node/npm, Vitest, `renderToStaticMarkup` component rendering (no
  jsdom/testing-library), Next.js 16.4.6 production build.

## 2. Commands and results

| Command | Result |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest` | **330 passed, 2 warnings** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_workforce_workflow.py` | **10 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m alembic heads` | `0025_workforce (head)` — single head |
| `frontend/npm run typecheck` | clean |
| `frontend/npm run lint` | clean (0 errors, 0 warnings) |
| `frontend/npm test` | **39 files, 160 tests passed** |
| `frontend/npm run build` | success; 24 static pages; new routes present |

Warnings are pre-existing and non-failing: a Starlette `httpx` deprecation notice
and a SQLite expression-index reflection notice. Neither affects behavior under
test.

## 3. Backend coverage: `tests/test_workforce_workflow.py`

| Test | What it proves |
|---|---|
| `test_application_submission_duplicate_and_role_guards` | Only CITIZEN may apply; duplicate applications rejected; strict schemas |
| `test_pending_applicant_cannot_use_worker_workspace` | Pending applicants have no worker operational access |
| `test_admin_approval_grants_worker_role_and_audits` | Approval grants WORKER through the audited service, activates profile, emits notification and audit events, immutable audit API |
| `test_rejection_and_additional_information_require_note` | Decision-specific note requirement; requester sees correct status |
| `test_citizen_cannot_approve_and_worker_cannot_approve_self` | ADMIN-only review and self-review guard |
| `test_full_lifecycle_from_report_to_resolution` | VERIFIED → ASSIGNED → ACCEPTED → IN_PROGRESS → COMPLETION_SUBMITTED → VERIFIED_COMPLETED → RESOLVED with incident status events and notifications |
| `test_assignment_guards_and_ownership` | Wrong-status transitions rejected; worker cannot act on another worker's assignment |
| `test_suspended_worker_is_ineligible_and_loses_access` | Suspension removes operational access and eligibility |
| `test_admin_overview_uses_real_counts` | Overview reads real incident/application/worker counts; citizen forbidden |
| `test_audit_metadata_is_persisted_and_scrubbed` | Regression: audit detail persists and sensitive keys are removed |

Structural migration/model tests were updated for the new head and six new tables:
`tests/db/test_migrations.py`, `tests/db/test_models.py`.

## 4. Frontend coverage

| Test file | What it proves |
|---|---|
| `lib/auth/routing.test.ts` | Protected paths include the new routes; distinct CITIZEN/WORKER/ADMIN navigation; `canAccessPath` and `homePathForRole` behavior; open-redirect protection |
| `lib/api/workforce.test.ts` | Every API helper sends the correct path, HTTP method, encoded filters and JSON body matching the backend schemas |
| `components/workforce/workforce-ui.test.tsx` | Status labels, tone mapping, and explicit loading/empty/error/status presentation states |

Verified together with the above: typecheck, lint, and a production build in
which `/admin`, `/worker`, `/workforce/apply` and `/workforce/status` are emitted
as static routes.

## 5. Defects found and fixed during this sprint

1. Unbound `previous` in `transition_incident()` after extending the state machine.
2. SQLAlchemy reserved-name warning for `WorkforceEvent.metadata`; mapped as `detail`.
3. SQLite double-prefixed CHECK constraint names during migration upgrade.
4. Audit event written before flush produced null `entity_id`.
5. Pydantic mismatch between ORM `worker_id` and schema `worker_profile_id`.
6. Missing `IncidentAssignment.events` relationship.
7. Wrong model used for response validation (`WorkforceEvent.model_validate`).
8. Citizen assignment list returned 404 instead of an explicit 403.
9. `ApiRequester` imported from a module that does not export it.
10. New React Compiler lint rule rejected synchronous `setState` in effects.
11. Existing routing test assumed workers and admins had identical navigation.
12. **Audit metadata silently dropped**: `emit()` passed `metadata=` while the
    mapped attribute is `detail`, so the database stored `{}`. Fixed and covered
    by a DB round-trip regression test.

## 6. Limitations — not claimed as verified

- No PostgreSQL/PostGIS integration suite; RLS/trigger behavior on a live provider
  was not executed.
- No browser E2E with real accounts; interactive workflows were verified by
  component rendering, API contract tests and a production build only.
- No production data, migration, user creation, role grant or pilot activation.
- No external notification delivery test (email/push not configured).
