# Admin & Worker RBAC and Security Boundaries

Date: 2026-11-26. Scope: the workforce authorization layer added for the Admin
Operations, Worker Approval & Incident Assignment Recovery Sprint.

## 1. Source of truth

Authorization is derived exclusively from the authenticated database profile.

1. Supabase verifies the JWT (signature, algorithm, issuer, audience, expiry) in
   `app/auth/jwt.py`.
2. `get_current_user()` resolves the token `sub` to a `Profile` row and attaches
   that row to the request.
3. `require_admin`, `require_active_user` and `require_active_worker` read
   `Profile.role`. No role claim, body field, query parameter or header can
   override it.

Consequence: a browser cannot grant itself WORKER or ADMIN, and changing a role
requires the existing audited `change_profile_role()` service.

## 2. Dependencies

| Dependency | Additional requirements | Failure |
|---|---|---|
| `require_active_user` | verified profile, active flag | 401 / 403 |
| `require_admin` | `Profile.role == ADMIN` | 403 `insufficient_role` |
| `require_active_worker` | `role == WORKER`, `WorkerProfile` exists, `status == ACTIVE` | 403 `insufficient_role` / `worker_profile_required` / `worker_suspended` |

`require_active_worker` is stricter than the legacy `require_worker`. Role alone
is insufficient: a suspended worker loses operational access immediately because
the `WorkerProfile.status` check is evaluated on every request.

## 3. Privileged flows

### Worker approval

- Only a CITIZEN may submit an application; one application per applicant.
- Only an ADMIN may review. Rejection and information requests require a note.
- Approval is atomic and calls `change_profile_role(..., WORKER)`, which already
  enforces admin-only access, self-change protection and last-admin protection,
  and writes a role-change audit event.
- A `WorkerProfile` is then created/activated. There is no separate "make worker"
  endpoint and no role value accepted from a client payload.

### Assignment and ownership

- Only an ADMIN can see candidates, assign, reassign or cancel.
- Worker mutations (`accept`, `decline`, `start`, `progress`, `complete`) call
  `_get_assignment()` which checks `assignment.worker_id == worker.id` before any
  state change. A worker cannot act on another worker's assignment.
- A worker's assignment list is scoped by `worker_id`, not merely by role.
- ADMIN can act across all assignments and verify completion.

`verify(approve=false)` sends work back to `IN_PROGRESS` for rework and does not
resolve the incident. Only an ADMIN may move an incident to `RESOLVED`.

## 4. Database-level protections

- Row-level security and ACL grants follow the project's established migration
  pattern. Migration `0025_workforce` enables RLS on all six new tables and
  grants read-only `SELECT` to the authenticated role on PostgreSQL; writes go
  through the application services using the trusted DB role.
- RLS triggers on `profiles` block browser-side role changes (existing
  migrations `0002_auth_rls.py`, `0003_acl_hardening.py`).
- The migration is additive: no seed rows, no destructive DDL, single Alembic
  head `0025_workforce`.

## 5. Audit and notification safety

- `workforce_events` is append-only in the application: only `emit()` writes;
  there is no update or delete endpoint.
- `_safe_metadata()` drops any key whose name contains password, token, secret,
  authorization, signed URL, storage path, credentials or access key, and only
  allows primitive/UUID values. Nested objects are discarded.
- The stored payload is written to the mapped `detail` attribute (DB column
  `metadata`); a regression test proves the value round-trips and sensitive keys
  are removed.
- Notifications use a closed `LIFECYCLE_KINDS` set and contain no credentials or
  private evidence URLs. The only mutating notification operation is marking one's
  own notification read.

## 6. Frontend boundary

`frontend/src/lib/auth/routing.ts` separates ADMIN, WORKER and CITIZEN navigation,
and `AuthGuard` redirects users away from modules their role cannot use. This is
**UX only**. Every API call is independently authorized by the backend. A
successful client-side guard is not evidence of server-side authorization; the
backend tests in `tests/test_workforce_workflow.py` are the authority for that.

## 7. Residual risks and honest limitations

- No PostgreSQL/PostGIS integration test was run; RLS and trigger behavior on the
  production provider is verified by code inspection and migration structure
  only, not by executing against a live database.
- The app's DB role and least-privilege grants remain an operator concern and are
  unchanged by this work.
- No production write, migration execution, user creation, role grant or pilot
  activation was performed.
- External notification delivery (email/push) is not configured; in-app messages
  are the only implemented delivery channel.
