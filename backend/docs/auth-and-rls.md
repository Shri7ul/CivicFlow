# Authentication, authorization, and RLS

This document describes the Phase 1 identity boundary and the Supabase-specific
database policies. It is intentionally limited to database and auth behavior.

## Roles

CivicFlow has exactly three application roles:

| Role | Profile provisioning | Backend access | Supabase RLS intent |
| --- | --- | --- | --- |
| `CITIZEN` | Default for every new profile | Own profile | Own profile, own incidents/evidence, public reference data, own scenarios |
| `WORKER` | ADMIN role change only | Worker/admin dependencies | Citizen reads plus worker incident, risk-assessment, and scenario visibility |
| `ADMIN` | ADMIN role change only | Admin dependencies | Worker visibility plus all profiles and role-change audits |

The frontend does not grant roles. A role claim, `user_metadata`, or
`app_metadata` supplied by the browser is ignored during provisioning. New
profiles are always inserted with `role = CITIZEN`.

## Identity flow

1. The browser signs in with Supabase Auth and receives a short-lived access
   token.
2. The frontend sends `Authorization: Bearer <token>` to FastAPI.
3. `SupabaseTokenVerifier` verifies the signature and validates `exp`, `iat`,
   `sub`, `aud`, and `iss`.
4. `get_current_profile` loads the application profile by the verified `sub`
   UUID and rejects missing or inactive profiles.
5. `require_role` / `require_admin` / `require_worker` enforce the application
   role centrally.
6. If no profile exists, the frontend calls `POST /api/v1/auth/provision`. The
   service creates a `CITIZEN` profile idempotently.

### JWT verification

- Asymmetric projects use the Supabase JWKS endpoint. `PyJWKClient` caches keys
  and refetches when a token references an unknown key, supporting rotation.
- Legacy HS256 shared-secret verification is intentionally unsupported. The
  backend uses the project's asymmetric JWKS (ES256/RS256) only, so no JWT
  signing secret is configured or needed.
- A token is never accepted from a decode-only path. Unsupported algorithms,
  malformed tokens, invalid signatures, expired tokens, wrong audience, wrong
  issuer, missing required claims, and invalid subject UUIDs are rejected.
- Rejection logging records only a classification such as `expired_token`; it
  never records the token, claims, or secret.

### Required configuration

```dotenv
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
# Optional; derived from SUPABASE_URL by default:
# SUPABASE_JWT_ISSUER=https://PROJECT_REF.supabase.co/auth/v1
# SUPABASE_JWKS_URL=https://PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json
```

Production startup requires `SUPABASE_URL`. URLs must use HTTPS outside
localhost/127.0.0.1.

## Profile provisioning and role management

`POST /api/v1/auth/provision`:

- Requires a valid access token.
- Creates only a `CITIZEN` profile.
- Returns the existing profile on repeat calls.
- Handles concurrent insert races with a unique-key retry.
- Rejects inactive accounts.

`PATCH /api/v1/auth/me`:

- Allows only `full_name` and `phone`.
- Rejects unknown fields, including `role`, `is_active`, and `id`.
- Cannot change role or activation state.

`PATCH /api/v1/admin/profiles/{profile_id}/role`:

- Requires an active `ADMIN`.
- Rejects self-role changes.
- Protects the last active administrator at the service layer.
- Writes a `role_change_audits` row in the same transaction.
- Returns the updated profile.

## Supabase RLS

Migration `0002_auth_rls.py` enables RLS on the original 13 tables and creates
the policies below. Migration `0004_incident_lifecycle.py` adds
`incident_status_events` with its own SELECT policy, bringing the total to 14
application tables and 18 application policies. Migration `0005` adds evidence
constraints and a private Storage bucket; it does not add an application policy.

| Table | Policy | Command | Applies to |
| --- | --- | --- | --- |
| `profiles` | `profiles_select_self` | SELECT | Self or admin |
| `profiles` | `profiles_update_self` | UPDATE | Self only |
| `departments` | `departments_read_authenticated` | SELECT | Active rows or admin |
| `incidents` | `incidents_read_owner_or_staff` | SELECT | Reporter, worker, or admin |
| `incidents` | `incidents_insert_own_open` | INSERT | Reporter, `OPEN`, unassigned |
| `incident_evidence` | `evidence_read_visible_incident` | SELECT | Evidence on a visible incident |
| `incident_evidence` | `evidence_insert_visible_incident` | INSERT | Legacy policy; direct INSERT grant is revoked by `0005` |
| `incident_clusters` | `clusters_read_authenticated` | SELECT | Authenticated |
| `incident_cluster_members` | `cluster_members_read_authenticated` | SELECT | Authenticated |
| `infrastructure_assets` | `assets_read_authenticated` | SELECT | Active rows or admin |
| `dependency_edges` | `dependencies_read_authenticated` | SELECT | Authenticated |
| `risk_cells` | `risk_cells_read_authenticated` | SELECT | Authenticated |
| `risk_assessments` | `risk_assessments_read_staff` | SELECT | Worker or admin |
| `scenarios` | `scenarios_read_owner_or_staff` | SELECT | Owner, worker, or admin |
| `scenarios` | `scenarios_insert_own_draft` | INSERT | Owner, `DRAFT` only |
| `scenario_results` | `scenario_results_read_visible_scenario` | SELECT | Results of a visible scenario |
| `role_change_audits` | `role_audits_read_admin` | SELECT | Admin only |
| `incident_status_events` | `incident_status_events_read_visible_incident` | SELECT | Reporter, worker, or admin (added by `0004`) |

The migration also grants the minimum table privileges used by those policies
to Supabase's `authenticated` role. Profile updates are column-limited to
`full_name` and `phone`. There is no `anon` grant.

### ACL least privilege (`0003_acl_hardening`)

Supabase projects can inherit broad default privileges for `anon` and
`authenticated`. Migration `0003_acl_hardening.py` revokes all privileges on
the 13 application tables present at that revision from both roles, then
restores only:

- `authenticated`: `SELECT` on all 13 tables, `INSERT` on `incidents`,
  `incident_evidence`, and `scenarios`, and `UPDATE(full_name, phone)` on
  `profiles`.

Migration `0004_incident_lifecycle.py` applies the same least-privilege rule to
the new `incident_status_events` table: `anon` receives nothing and
`authenticated` receives `SELECT` only. The lifecycle history is written by the
backend, never directly by a browser session.

Migration `0005_map_evidence_storage.py` revokes `INSERT` on
`incident_evidence` from both `authenticated` and `anon`, leaving
`authenticated` with `SELECT` only. Evidence writes now go exclusively through
the backend service role. Migration `0006_incident_intelligence.py` applies the
same rule to `incident_relationships`: `authenticated` receives `SELECT` only,
`anon` receives nothing, and review writes stay backend-only. Migration
`0009_urban_risk_engine.py` adds `risk_model_runs` and `risk_cell_snapshots`
with staff-only RLS (`is_worker_or_admin()`), SELECT-only authenticated grants,
and no browser INSERT path. `0010_risk_factor_default.py` aligns the snapshot
factor-contribution default with the JSON-array contract. After `0010`,
authenticated has `SELECT` on all 17
application tables, `INSERT` on `incidents` and `scenarios`, and column UPDATE
on `profiles.full_name/phone` only.

`anon` has no application-table privileges. `service_role` is intentionally
unchanged because it is the trusted server identity. RLS remains enabled on all
17 application tables after `0010`, and the column grants work with the
corresponding policies. Relationship visibility requires staff access or a pair
owned by the caller; citizen relationship listings additionally filter in the
service layer.

### Private Storage

`0005` creates the private `incident-evidence` bucket with a 10 MB limit and a
JPEG/PNG/WebP MIME allowlist. The migration attempts a visibility-scoped
`storage.objects` SELECT policy, but the hosted table is owned by
`supabase_storage_admin`; the migration role (`postgres`) cannot create that
policy. The attempt is skipped with a notice. There is no INSERT/UPDATE/DELETE
client policy, so direct browser Storage reads are deny-all. Backend-issued
signed URLs remain scoped by incident authorization. See
[evidence.md](evidence.md) for the operational policy and verification detail.

### Privilege guard trigger

`profiles_protect_privileged_fields` runs before updates to `profiles`. When an
end-user JWT is present (`auth.uid() IS NOT NULL`), it rejects changes to:

- `id`
- `role`
- `is_active`

The backend's privileged role-change path is not an end-user request and is
authorized by FastAPI before it writes the audit row. Direct end-user table
access can never promote itself through Supabase.

### Helper functions

`current_app_role()`, `is_admin()`, and `is_worker_or_admin()` are `STABLE`,
`SECURITY DEFINER` SQL functions with a fixed `search_path` (`public, pg_temp`).
They read the caller's active profile role and are used by policies. They do not
accept a caller-supplied profile ID.

### RLS is not the backend's authorization layer

FastAPI connects to PostgreSQL using the configured database credentials, not
an end-user Supabase JWT. It therefore does not rely on RLS for request
authorization. RLS protects direct Supabase client access. Every FastAPI
endpoint must still use the centralized dependencies described above.

## Applying the schema

Use Alembic as the source of truth. Do not run `Base.metadata.create_all()` in
production.

```powershell
cd backend

# Direct Supabase connection (recommended for DDL):
$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://postgres:...@db.PROJECT_REF.supabase.co:5432/postgres"

.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

The RLS migration is Supabase-specific and expects the `auth` schema and
`authenticated` role. Run it against Supabase, not a bare PostgreSQL database.
The seed refuses to run when `APP_ENV=production`.

Render the PostgreSQL SQL without connecting:

```powershell
$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/civicflow"
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Verification boundary

The configured Supabase project was validated live on 2026-11-23:

- Alembic upgraded the project through `0010_risk_factor_default`.
- PostgreSQL 17.12 was reachable over TLS.
- PostGIS 3.3.7 is installed in `public`.
- All 17 application tables, 5 GIST indexes, 21 application policies, 9
  triggers, 19 foreign keys, and 7 unique constraints exist. The private
  `incident-evidence` bucket exists with a 10 MB limit and image allowlist; no
  `storage.objects` policy exists for it on this hosted project.
- RLS was exercised transactionally with synthetic JWT claims for anonymous,
  Citizen, Worker, and Admin identities. All test rows were rolled back.
- ACL counts were verified after `0010`: anonymous table privileges are zero;
  authenticated has SELECT on all 17 application tables, INSERT on 2, column
  UPDATE on the two profile fields, and SELECT only on `incident_evidence`,
  `incident_relationships`, `risk_model_runs`, and `risk_cell_snapshots`; `service_role` was not changed. A transactional real-role test confirmed that Citizen sees only
  lifecycle events for their own incident, another Citizen sees none, and
  Worker sees the event.
- Isolated real Auth users were created through the Admin API, signed in, and
  used for provisioning, `/auth/me`, role changes, and browser session tests.
  Sign-in issued real ES256 tokens accepted through the live JWKS. Public
  self-service signup returned HTTP 429 because the project's email send rate
  limit was exhausted; confirmation enforcement was verified separately with
  an unconfirmed user. All test users, profiles, and audits were deleted
  afterward, returning counts to zero.
- Phase 3 live validation confirmed private Storage upload, signed URL download,
  direct-read denial, cross-Citizen denial, and cleanup of every disposable user,
  profile, incident, status event, evidence row, and Storage object.
- Phase 4 live validation confirmed duplicate suggestions, cross-Citizen
  candidate/relationship privacy, staff-only review, unique relationship
  persistence, opaque 404s, infrastructure proximity, inferred-impact labeling,
  and cleanup of all disposable relationships, assets, and edges.
- The profile privilege trigger rejected direct Citizen and Admin role and
  activation changes.
- `alembic check` reports no new upgrade operations.

Live boundaries and known low-risk findings:

- Public self-service signup could not complete because the project returned
  HTTP 429 for the email send rate limit. Confirmation enforcement was verified
  with an unconfirmed Admin-created user; no inbox confirmation link was read.
- Supabase default ACLs on some older tables still carry inherited `TRUNCATE`,
  `REFERENCES`, and `TRIGGER` privileges for `service_role`; `0003` removed them
  from `anon`/`authenticated`. RLS does not protect `TRUNCATE`, although
  PostgREST does not expose it.
- Some older PostgreSQL CHECK constraint names remain double-prefixed by the
  project naming convention. The new Phase 4 confidence/side constraints are
  normalized by `0007`/`0008`; the older ones are present and enforced, and only
  their names differ from model metadata.
- Two older enum-backed VARCHAR columns are one character wider than the model
  enum maximum (`dependency_type` 12 vs 11, `risk_entity_type` 21 vs 20). The
  wider storage is safe.

Do not describe unexecuted checks as passed. The Phase 4 live and browser
results above were executed against the configured Supabase project with
disposable users and cleaned up afterward.
