# CivicFlow progress

Last updated: 2026-11-24

## Status

| Phase / goal | Status | Evidence |
| --- | --- | --- |
| Phase 0 — foundation | ACCEPTED | Health, config, errors, CORS, frontend shell, scripts |
| Phase 1 / Goal 03 — database architecture | ACCEPTED | 14 tables, PostGIS types/indexes, Alembic, seed |
| Phase 1 / Goal 04 — authentication/authorization | ACCEPTED | JWKS JWT verification, RBAC, provisioning, audited roles |
| Phase 1.5 — live Supabase integration | ACCEPTED (signup boundary noted) | Live migration, RLS matrix, real ES256 sign-in, browser session |
| Phase 1.6 / Goal 1.6.1 — DB least privilege | ACCEPTED | Migration `0003_acl_hardening`; live ACL counts |
| Phase 1.6 / Goal 1.6.2 — remove legacy HS256 | ACCEPTED | Config, verifier, tests, docs updated; ES256/RS256 only |
| Phase 1.6 / Goal 1.6.3 — real auth acceptance | ACCEPTED (signup boundary noted) | Real users, ES256, provisioning, role change, UI session, cleanup |
| Phase 1.6 / Goal 1.6.4 — docs/report | COMPLETE | README, auth/RLS docs, this progress log |
| Phase 2 / Goal 05 — incident API/lifecycle | ACCEPTED | Migration `0004`, API, live API validation |
| Phase 2 / Goal 06 — incident frontend | ACCEPTED | `/incidents`, `/incidents/new`, `/incidents/[id]`, live browser flow |
| Phase 3 — spatial map, clustering, evidence | ACCEPTED (storage-policy limitation) | Migration `0005`, map/evidence live API + browser runs, 112 backend / 44 frontend tests |

The working tree is intentionally uncommitted. No push was performed.

## Phase 3 implementation checklist

### Repository audit

- [x] Re-read README, progress tracker, architecture, models, migrations, auth.
- [x] Confirmed existing Phase 2 APIs, PostGIS bbox filtering, and evidence table.
- [x] Confirmed no MapLibre dependency and no storage bucket/policies existed.
- [x] Confirmed `python-multipart` and Supabase Storage configuration were absent.

### Spatial map

- [x] Install and integrate MapLibre GL JS with Next.js.
- [x] Add central Dhaka default viewport.
- [x] Create protected `/map` route and navigation entry.
- [x] Render incident GeoJSON source with native MapLibre layers.
- [x] Add severity fill, status stroke, category labels, and legend.
- [x] Add clustering + cluster expansion.
- [x] Add marker selection, selected-marker highlight, and detail preview.
- [x] Add list/map synchronization.
- [x] Add viewport state, debounce, abort/stale-response protection.
- [x] Combine viewport with status/category/severity/department/search filters.
- [x] Add loading, error, retry, empty, and result-limit states.
- [x] Add zoom/reset/location controls, attribution, and responsive layout.
- [x] Add map-based location picker to incident reporting.

### Evidence

- [x] Add `0005` migration for evidence constraints, index, ACL tightening.
- [x] Create private `incident-evidence` Storage bucket via migration.
- [~] Add Storage RLS policy scoped to incident visibility. Migration attempts
  it conditionally; hosted `storage.objects` is owned by
  `supabase_storage_admin`, so the policy is skipped. There is no client write
  policy and direct reads are deny-all; backend signed URLs remain authorized.
- [x] Add backend Storage client with service-role-only upload/sign/delete.
- [x] Add upload endpoint with count, size, MIME/signature, and filename validation.
- [x] Persist evidence metadata and return safe metadata.
- [x] Add signed URL endpoint after backend authorization.
- [x] Add evidence gallery, upload, progress, retry, and safe viewing to detail.
- [x] Verify Citizen/Worker/Admin API authorization and unauthorized denial.

### Security and quality

- [x] Preserve Auth, RBAC, RLS, and ACL hardening.
- [x] Keep service-role key server-only.
- [x] Validate no path traversal or arbitrary MIME acceptance.
- [x] Add backend tests for spatial/evidence/authorization/storage.
- [x] Add frontend helper/API/upload tests.
- [x] Run typecheck, lint, Vitest, build, pytest, Alembic checks.
- [x] Run live storage/map/browser validation and clean up test data.
- [x] Update README, API docs, spatial/evidence docs, env docs, and acceptance report.

## Phase 2 scope implemented

- `POST /api/v1/incidents` for authenticated reporting with validated WGS84
  coordinates and optional address.
- `GET /api/v1/incidents` with pagination, status/category/severity/department
  filters, text search, and a PostgreSQL/PostGIS bounding box.
- `GET /api/v1/incidents/{id}` with lifecycle history and evidence metadata.
- `PATCH /api/v1/incidents/{id}` with owner/staff edit rules.
- `POST /api/v1/incidents/{id}/status` for `WORKER`/`ADMIN`, enforcing
  `OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED` (plus
  `OPEN → IN_PROGRESS`), department requirements, `resolved_at`, and immutable
  `incident_status_events`.
- `GET /api/v1/departments` for active assignment options.
- Frontend incident queue, report form, detail view, inline editing, staff
  action panel, and history timeline.
- Route protection extended to `/incidents/**`; backend remains the
  authorization boundary.

## Phase 3 scope implemented

### Map and spatial query

- `/map` protected route, client-only MapLibre dynamic import, OSM raster base
  layer, Dhaka default viewport, zoom/reset/geolocation/attribution controls.
- One GeoJSON source and native layers: clusters + counts, severity fill, status
  ring, category abbreviation labels, selected ring. No DOM marker per incident.
- Cluster expansion, marker selection preview, list/map selection sync.
- `GET /api/v1/incidents` viewport query uses all four bbox parameters plus
  status/category/severity/department/search. 300 ms debounce,
  `AbortController`, and request IDs prevent stale results.
- Report form location picker clicks place a marker and set coordinates.

### Evidence

- `POST /api/v1/incidents/{id}/evidence`, `GET .../evidence`, and
  `GET .../evidence/{id}/url`.
- Server-side signature detection for JPEG/PNG/WebP, 1–5 files, 10 MB/file,
  sanitized display names, server-generated object keys, rollback/cleanup.
- Private bucket and backend service-role upload; signed preview URLs expire
  after 300 seconds by default.
- Detail-page gallery with client preflight, multipart progress, retry, signed
  previews, and link refresh.

## Verification commands

```powershell
# Backend
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check

# Frontend
cd ..\frontend
npm run typecheck
npm run lint
npm test
npm run build

# End-to-end local checks
cd ..
.\scripts\verify.ps1
```

Latest recorded results:

- Backend: **112 passed**.
- Alembic: live revision `0005_map_evidence_storage`; `alembic check` reports
  **No new upgrade operations detected** (custom PostGIS type warnings only).
- Frontend: typecheck, ESLint, **44 tests** (13 files), and production build
  pass.
- `scripts/verify.ps1` passes.

## Live validation evidence

- Live PostgreSQL 17.12 + PostGIS 3.3.7, all migrations applied through
  `0005_map_evidence_storage`.
- 14 application tables, 18 application RLS policies, 8 triggers, 14 foreign
  keys, 5 unique constraints, 4 GIST indexes. RLS enabled on all 14 application
  tables. New evidence MIME/size constraints and composite index present.
- Private `incident-evidence` Storage bucket exists with `public=false`,
  10 MB limit, and JPEG/PNG/WebP allowlist.
- ACLs after `0005`: `anon` has no application-table privileges;
  `authenticated` has SELECT on 14 tables, INSERT on incidents and scenarios,
  column UPDATE only on `profiles.full_name/phone`, and no direct INSERT on
  `incident_evidence`.
- Real isolated Auth users completed sign-in with ES256 tokens, backend JWKS
  verification, profile provisioning, `/auth/me`, role changes, and cleanup.
- Real API validation covered report creation, Citizen scoping, Worker/Admin
  visibility, text/bbox filters, edit locking after acknowledgement, department
  assignment, full lifecycle, history, invalid transitions, and 403/404/409
  boundaries.
- Phase 3 live API validation (real users, real Storage):
  bbox query, upload, server-side MIME detection, filename sanitization,
  server-generated path, detail/list metadata, signed URL bytes, direct storage
  read denial, cross-Citizen denial, spoofed MIME rejection, empty-file
  rejection, and unauthenticated rejection all passed.
- Phase 3 live headless-Chrome validation:
  sign-in, protected map route, MapLibre canvas, 3 rendered points, marker
  selection preview, list sync, combined filters/empty state/reset, viewport
  empty/reset, native cluster expansion, geolocation marker, signed evidence
  preview, multipart upload with new preview, report-map coordinate picker, and
  mobile layout all passed.
- Transactional real-role RLS validation confirmed that `incident_status_events`
  is visible to the reporter and staff, and hidden from another Citizen.
- All disposable Auth users, profiles, incidents, status events, evidence rows,
  Storage objects, and the temporary department were deleted. Remaining counts
  were zero.

## Known boundaries

- Public self-service `/auth/v1/signup` returned HTTP 429 because the Supabase
  project's email send rate limit was exhausted during earlier validation. The
  confirmation rule was verified with an unconfirmed Admin-created user.
  Confirmation links were not read from an inbox.
- Bounding-box filtering is PostgreSQL/PostGIS-only by design; the SQLite test
  dialect returns `400 spatial_filter_unsupported`.
- The hosted `storage.objects` table is owned by `supabase_storage_admin`. The
  migration role cannot create the intended visibility SELECT policy, so the
  migration skips it with a notice. Direct client Storage access is therefore
  deny-all (verified), which is stricter than scoped reads; signed URL issuance
  remains backend-authorized. See `backend/docs/evidence.md` for the dashboard
  policy SQL and security note.
- No duplicate detection, risk scoring, dependency analysis, scenario simulation,
  notification delivery, admin dashboard, or department management.
- Departments must be seeded or provisioned out of band.
- OSM public raster tiles are used for this phase; production tile usage must be
  reviewed separately.
- No commit or push was made. Environment files remain untracked/ignored.

## Suggested next goals

1. Apply the documented `storage.objects` visibility policy through a role that
   owns the hosted table, then verify direct signed-URL-free access.
2. Duplicate detection and incident clusters using PostGIS distance/time windows.
3. Infrastructure dependency and risk engines.
4. Scenario simulation and notification delivery.
5. Admin operations UI, department management, and audit export.
