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
| Phase 4 — incident intelligence | ACCEPTED | Migration `0006`–`0008`, intelligence/relationship/impact APIs, live API + browser runs, 122 backend / 51 frontend tests |

Phase 3 was committed and pushed as `69cf003`
(`feat(civicflow): complete phase 3 spatial intelligence`). The Phase 4 working
tree is intentionally uncommitted; no Phase 4 push was performed.

## Phase 4 implementation checklist

### Repository audit and scope

- [x] Re-read the roadmap, progress log, README, models, migrations, and tests.
- [x] Confirmed no intelligence engine, relationship persistence, or duplicate
  review API existed.
- [x] Confirmed infrastructure/dependency tables existed but held only explicitly
  development-only seed rows, not authoritative municipal data.
- [x] Chose an explainable, human-reviewable scope instead of fabricating datasets.

### Correlation and duplicate detection

- [x] Add deterministic spatial, temporal, category, text, and severity signals.
- [x] Add configurable radius, window, text, confidence, candidate, and impact limits.
- [x] Separate duplicate candidates from related candidates.
- [x] Return per-signal weights, contributions, explanations, reasons, and confidence.
- [x] Never auto-merge, delete, or mutate incidents from suggestions.
- [x] Preserve Citizen visibility in candidate retrieval and relationship listing.
- [x] Avoid excessive queries with bounded PostGIS candidate retrieval and limits.

### Persistence and review

- [x] Add `incident_relationships` with canonical ordering, unique pair/type,
  confidence range, self-link CHECK, FKs, indexes, and timestamps.
- [x] Add `0006` migration, RLS, SELECT-only authenticated grant, and trigger.
- [x] Normalize early Phase 4 CHECK names with `0007`/`0008`.
- [x] Add WORKER/ADMIN review endpoint with idempotent upsert by canonical pair/type.
- [x] Persist reviewer, review time, confidence, signals, and note.
- [x] Reject self-links and non-staff review; map concurrent conflicts to 409.

### Infrastructure and impact foundation

- [x] Add authenticated active-infrastructure reference endpoint.
- [x] Use PostGIS spatial predicates and geography distance with WGS84 handling.
- [x] Return nearby asset distance and dependency-link count.
- [x] Traverse dependency edges breadth-first with depth/node bounds and decaying confidence.
- [x] Label root proximity as `GEOSPATIAL_ASSOCIATION` and graph paths as
  `INFERRED_POTENTIAL`; state that neither is observed damage.
- [x] Document seed-data provenance and missing authoritative asset feed.

### Frontend

- [x] Add typed intelligence API client, types, and formatting helpers.
- [x] Add an incident-detail intelligence panel without removing existing UI.
- [x] Show duplicate and related suggestions with confidence, reasons, signals,
  candidate links, and explicit “decision support” framing.
- [x] Add staff-only confirm/dismiss review controls and reviewed-relationship cards.
- [x] Show infrastructure proximity and impact paths with type/confidence/rationale.
- [x] Add loading, error/retry, empty, threshold, and limitation states.
- [x] Add API/helper tests for serialization, formatting, and inference labels.

### Verification and documentation

- [x] Add backend unit/API/constraint/migration tests for intelligence.
- [x] Run full backend and frontend suites, typecheck, lint, and production build.
- [x] Run live API validation with disposable real users, assets, and dependency data.
- [x] Run live headless-Chrome validation of the rendered intelligence panel.
- [x] Clean up all disposable rows, users, assets, edges, and relationships.
- [x] Update README, backend/frontend READMEs, auth/RLS docs, and intelligence docs.

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

## Phase 4 scope implemented

### Intelligence API

- `GET /api/v1/incidents/{id}/intelligence` returns duplicate and related
  candidates, visible reviewed relationships, nearby infrastructure,
  dependency-aware potential impacts, thresholds, and limitations.
- Confidence combines distance (0.32), time (0.18), text (0.23), category
  (0.13), severity (0.04), and lifecycle status (0.10). Duplicate classification additionally requires
  the duplicate radius/window, compatible category, text threshold, and
  confidence threshold.
- Text matching is normalized token Jaccard plus sequence similarity. It is
  lexical and intentionally explainable, not an NLP/embedding model.
- `GET /api/v1/infrastructure/assets` exposes active assets to authenticated
  users. No external municipal feed is configured; repository seed assets are
  development-only.
- `GET`/`POST /api/v1/incidents/{id}/relationships` lists visible reviewed
  relationships and lets WORKER/ADMIN users confirm or dismiss a suggestion.
  Pairs are canonical/unique; re-review updates the same row.
- Impact depth `0` is a spatial association; graph-derived entries are
  `INFERRED_POTENTIAL`, decay in confidence, and explicitly disclaim observed
  damage/outage/cascade prediction.

### Persistence and security

- `incident_relationships` stores a canonical incident pair, relationship type,
  status, confidence, signals, note, reviewer, and timestamps.
- Self-relationships are rejected in the API and database.
- RLS limits reads to staff or a pair owned by the caller; `authenticated` has
  SELECT only. Relationship writes remain backend-only.
- Citizens cannot infer another Citizen's incident through candidates,
  intelligence, relationships, or opaque 404 behavior.
- Concurrent review conflicts return `409 relationship_conflict`.

### Frontend

- Incident detail includes an intelligence panel with decision-support framing,
  duplicate/related candidate cards, confidence/reasons/signal details,
  staff-reviewed relationship cards, nearby infrastructure, potential impact
  paths, thresholds, and data limitations.
- Staff see confirm/dismiss review controls; Citizens see read-only context.
- Existing report, lifecycle, map, and evidence flows are preserved.

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

- Backend: **122 passed**.
- Alembic: live revision `0008_confidence_check_name`; `alembic check` reports
  **No new upgrade operations detected** (custom PostGIS type warnings only).
- Frontend: typecheck, ESLint, **51 tests** (15 files), and production build
  pass.
- `scripts/verify.ps1` passes (run after the Phase 4 verification suite).

## Live validation evidence

- Live PostgreSQL 17.12 + PostGIS 3.3.7, all migrations applied through
  `0008_confidence_check_name`.
- 15 application tables, 19 application RLS policies, 9 triggers, 17 foreign
  keys, 6 unique constraints, 4 GIST indexes. RLS enabled on all 15 application
  tables. Evidence MIME/size constraints, the evidence composite index, and
  normalized Phase 4 relationship CHECKs are present.
- Private `incident-evidence` Storage bucket exists with `public=false`,
  10 MB limit, and JPEG/PNG/WebP allowlist.
- ACLs after `0005`: `anon` has no application-table privileges;
  `authenticated` has SELECT on all 15 application tables, INSERT on incidents
  and scenarios, column UPDATE only on `profiles.full_name/phone`, and no direct
  INSERT on `incident_evidence` or `incident_relationships`.
- Real isolated Auth users completed sign-in with ES256 tokens, backend JWKS
  verification, profile provisioning, `/auth/me`, role changes, and cleanup.
- Real API validation covered report creation, Citizen scoping, Worker/Admin
  visibility, text/bbox filters, edit locking after acknowledgement, department
  assignment, full lifecycle, history, invalid transitions, and 403/404/409
  boundaries.
- Phase 4 live API validation (disposable real users, assets, dependency edge):
  duplicate and related suggestions with explanations, cross-Citizen candidate
  privacy, staff-only review, relationship persistence/uniqueness, citizen
  relationship hiding, opaque 404 intelligence access, PostGIS asset proximity,
  inferred-impact labeling, authenticated asset listing, and cleanup to zero.
- Phase 4 live headless-Chrome validation:
  signed-in incident detail rendered the intelligence panel, duplicate
  candidate, explanation details, decision-support label, reviewed/empty
  infrastructure/impact states, thresholds, and limitations.
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
  Storage objects, relationships, infrastructure assets, dependency edges, and
  temporary departments were deleted. Remaining counts were zero.

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
- Correlation is lexical/heuristic and human-reviewed; there is no NLP or
  embedding model, automatic merge, or automatic incident mutation.
- Infrastructure proximity is a spatial association, and dependency paths are
  inferred graph associations, not observed damage/outage or a calibrated
  cascade prediction.
- The repository has no authoritative municipal asset feed; infrastructure rows
  are development seed data unless a deployment loads its own dataset.
- No risk scoring/H3 engine, scenario simulation, notification delivery, admin
  dashboard, or department management.
- Departments and authoritative infrastructure data must be loaded out of band.
- OSM public raster tiles are used for this phase; production tile usage must be
  reviewed separately.
- No commit or push was made. Environment files remain untracked/ignored.

## Suggested next goals

1. Apply the documented `storage.objects` visibility policy through a role that
   owns the hosted table, then verify direct signed-URL-free access.
2. Authoritative municipal asset/dataset ingestion with provenance and freshness.
3. Risk scoring and H3 risk cells built on incident/infrastructure history.
4. Scenario simulation, dependency optimization, and notification delivery.
5. Admin operations UI, department management, and audit export.
6. Re-run public signup -> email confirmation -> sign-in after the Supabase
   email rate limit resets.
