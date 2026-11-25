# CivicFlow — RBAC and Security Audit

Date: 2026-11-26
Scope: actual roles, permission boundaries, enforcement points, and security controls in the checked-out implementation and verified live headers.

## 1. Roles implemented (no new roles invented)

| Role | Source | Meaning |
| --- | --- | --- |
| `CITIZEN` | `backend/app/models/enums.py:8-11` | Default role assigned at provisioning. Can report and view own incidents. |
| `WORKER` | same | Authorized operator. Can view all incidents, change statuses, run planning/risk/validation workflows, submit/review field evidence. |
| `ADMIN` | same | Administrative. Can change roles, manage governance registries, configure operational resources, and approve sensitive reviews. |

`require_active_user` = any active profile. `require_worker` = WORKER or ADMIN. `require_admin` = ADMIN only (`backend/app/auth/dependencies.py:107-132`). Roles are read from the database `Profile`, never from untrusted client payloads or JWT claims.

## 2. Permission matrix (actual backend enforcement)

| Feature | Citizen | Worker | Admin | Enforcement |
| --- | --- | --- | --- | --- |
| Register / verify / log in | Allowed | Allowed | Allowed | Supabase Auth |
| Provision own profile (CITIZEN only) | Allowed | Allowed | Allowed | `POST /auth/provision`, `get_token_claims` |
| Report incident | Allowed | Allowed | Allowed | `require_active_user` |
| View own incidents | Allowed | Allowed | Allowed | `_assert_visible` filters by reporter |
| View all incidents | Denied (404 on other citizens) | Allowed | Allowed | `services/incidents.py:96-105,309-311` |
| Edit incident | Own, while OPEN | Until CLOSED | Until CLOSED | `services/incidents.py:173-237` |
| Change incident status | Denied | Allowed | Allowed | `require_worker` + `ALLOWED_TRANSITIONS` |
| Upload evidence | Own incident only | Own/assigned | All | `require_active_user` + ownership |
| Read risk cells / summary | Allowed (privacy-suppressed) | Allowed | Allowed | `risk.py`, suppression for citizens |
| Persist a risk run | Denied | Allowed | Allowed | `require_worker` on `POST /risk/runs` |
| Decision scenario CRUD / simulate | Denied | Allowed | Allowed | `require_worker` on all decision routes |
| Approve a decision review | Denied | Denied | Allowed | `reviews.py` decision = `require_admin` |
| Operations dashboard reads | Denied | Allowed | Allowed | `require_worker` |
| Operational config mutations | Denied | Denied | Allowed | `require_admin` |
| Validation reads | Denied | Allowed | Allowed | `require_worker` |
| Validation dataset create / research run | Denied | Denied | Allowed | `require_admin` |
| Change a user's role | Denied | Denied | Allowed | `admin.py` + self/last-admin guards |
| Pilot governance mutations | Denied | Mostly denied | Allowed | `phase10/11/14` dependencies + service-level separation of duties |

### Known policy inconsistency

`backend/app/api/v1/endpoints/phase10.py:3-4` documents "Mutating governance routes require ADMIN", but these mutating routes use `require_worker`:
- `POST /governance/reviews` — `:394-399`
- `POST /governance/reviews/{case_id}/decisions` — `:451-457`
- `POST /governance/correlation/candidates/{id}/reviews` — `:555-561`

This sprint corrects the docstring to match actual enforcement. It does **not** silently tighten permissions, because changing authorization semantics could break established workflows and would itself need a product decision. The permission matrix above records actual behavior.

## 3. Frontend enforcement

- `frontend/src/proxy.ts:15-40` redirects requests to protected prefixes when the auth cookie is missing. It explicitly states the backend verifies JWTs — route gating is UX, not authorization.
- `frontend/src/components/auth/auth-guard.tsx` handles unauthenticated/unconfigured/loading/error states.
- `frontend/src/components/auth/auth-nav.tsx:24-95` rendered every module link to every authenticated user. This sprint makes navigation role-aware. **Frontend hiding remains UX only; backend enforcement is authoritative.**
- Backend 401/403 responses were previously surfaced through generic page-level error text. This sprint adds explicit handling and dedicated UI states.

## 4. Security controls verified

| Control | Evidence | Status |
| --- | --- | --- |
| JWT verification | Asymmetric-only (RS256/ES256), requires `exp/iat/sub/aud/iss`, JWKS signature check (`auth/jwt.py:69-141`) | VERIFIED |
| No service-role in frontend | `lib/supabase/config.ts:26-33` rejects keys containing `service_role` | VERIFIED |
| Service role backend-only, `SecretStr` | `services/storage.py:35`, `core/config.py:66` | VERIFIED |
| Consistent error format, no stack traces | `core/exceptions.py:49-64`, `test_errors.py` | VERIFIED |
| Request ID + sanitized logging | `core/middleware.py`, `request_context.py` | VERIFIED |
| Security headers (HSTS, CSP, X-Frame-Options, Referrer-Policy) | Live response headers on both origins | VERIFIED |
| CORS validated config | `main.py:74-80`, `test_phase13_hardening.py` | VERIFIED |
| Production API docs disabled | live `GET /docs` → 404 | VERIFIED |
| Secrets not tracked | CI secret scan + `.gitignore`; only `.env.example` tracked | VERIFIED |
| RLS policies in migrations | `0002_auth_rls.py`, `0003_acl_hardening.py`, `0024_phase14_pilot.py` | PRESENT, enforcement operator-dependent |
| Least-privilege DB role | Docs report app uses `postgres`, bypassing RLS | REQUIRES OPERATOR ACTION |

## 5. Caveats explicitly not claimed

- No production authenticated request was made with a real user; RBAC is verified by backend tests, not browser E2E.
- Rate limiting is in-process and keyed on socket peer; behind a proxy clients can share a quota. No change to proxy-header trust is made here because that would weaken the spoofing protection without an explicit trusted-proxy configuration.
- No migration, RLS policy change, role change, or production data write was performed.
