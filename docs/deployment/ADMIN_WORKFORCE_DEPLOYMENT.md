# Admin & Workforce Deployment Notes

Date: 2026-11-26. Status: **prepared locally, not deployed**. This sprint did not
run a migration against production, write production data, create users, grant
roles or activate the pilot.

## 1. What changed for deployment

- New additive Alembic revision `backend/alembic/versions/0025_workforce.py`
  after `0024_phase14_pilot`.
- Six new tables: `worker_applications`, `worker_profiles`,
  `incident_assignments`, `incident_assignment_events`, `workforce_events`,
  `workforce_notifications`.
- Additive extensions to incident status CHECK constraints on `incidents.status`,
  `incident_status_events.from_status` and `incident_status_events.to_status`.
- New API router mounted at `/api/v1/workforce`.
- New frontend routes `/admin`, `/worker`, `/workforce/apply`, `/workforce/status`.

Migration graph was verified locally to have a single head: `0025_workforce (head)`.

## 2. Migration safety

- The revision is additive: `CREATE TABLE` only, no `DROP`, no data rewrite, no
  seed rows, no backfill that writes application data.
- RLS is enabled on each new table and read-only `SELECT` is granted to the
  authenticated role, matching the project's existing migration pattern.
- The SQLite upgrade/downgrade test exercises the revision end to end.
- `_replace_check()` handles historical double-prefixed SQLite constraint names
  while emitting the correct PostgreSQL DDL.

The migration has **not** been applied to the production Supabase database. Doing
so remains an explicit operator action and should follow the existing
backup/restore drill documented in `docs/operations/PHASE13_BACKUP_RECOVERY.md`.

## 3. Required environment

No new environment variables are introduced. Existing requirements still apply:

- Backend: `DATABASE_URL` (trusted application role), Supabase project URL, JWKS
  URL, JWT audience/issuer, `CORS_ORIGINS`, `APP_ENV`, `DEBUG`.
- Frontend: `NEXT_PUBLIC_API_BASE_URL`,
  `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_SITE_URL`.

No service-role key, secret or credential is added to source, docs or the client
bundle.

## 4. Operator deployment sequence

1. Take and verify a database backup using the documented recovery procedure.
2. Review `0025_workforce.py` and confirm the revision is the single Alembic head.
3. Apply migrations in the deployment environment (`alembic upgrade head`) using
   the trusted application role.
4. Deploy the Render backend from `main`; confirm `/api/v1/health` and
   `/api/v1/health/dependencies` return 200.
5. Deploy the Vercel frontend from `main`; confirm the four new routes render and
   unauthenticated access redirects to sign-in.
6. Verify CORS allows the Vercel origin and Supabase redirect allowlist is intact.
7. With real test accounts only: apply as worker → admin approves → worker sees
   `/worker` → admin assigns → worker accepts/completes → admin verifies →
   incident resolves. Confirm audit events and notifications appear.

No step above authorizes pilot activation. Step 7 uses ordinary accounts and
does not create production users by script.

## 5. Rollback

- Application rollback: redeploy the previous Render/Vercel commit. The new tables
  are unreferenced by the old build, so a code-only rollback is safe.
- Database rollback: `alembic downgrade 0024_phase14_pilot` drops the six new
  tables and reverts the status CHECK extensions. This destroys workforce data
  created while the new build was live, so take a backup first and treat it as a
  deliberate, destructive operation requiring operator approval.
- No automatic rollback is performed by this sprint.

## 6. Post-deploy checks

- `GET /api/v1/workforce/admin/overview` returns 403 for CITIZEN/WORKER and real
  counts for ADMIN.
- `GET /api/v1/workforce/workers/me` returns 403 for non-workers and for suspended
  workers.
- `GET /api/v1/workforce/events` is ADMIN-only and exposes `detail`, never
  credentials or private URLs.
- Suspended workers lose access without a redeploy (status is checked per request).

## 7. Honest status

Render/Vercel credentials and a production backup/restore drill are not available
in this environment. Deployment and live verification above are **not claimed as
performed**. The evidence for this sprint is local: full test suites, migration
graph validation, lint, typecheck, production build, API contract tests and the
audit artifacts.
