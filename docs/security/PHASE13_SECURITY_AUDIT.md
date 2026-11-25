# Phase 13 Security and Privacy Audit

Date: 2026-11-25
Scope: adversarial review of all Phase 13 changes plus the surrounding auth,
authorization, data-acquisition and deployment surface.

Status legend: **FIXED** (code + test), **MITIGATED** (control exists, residual
risk documented), **ADVISORY** (not fixed in this phase), **NOT_ASSESSED**,
**BLOCKED**.

## 1. Findings and disposition

| # | Finding | Severity | Evidence | Status |
| --- | --- | --- | --- | --- |
| S1 | No security headers on API responses (CSP, frame options, referrer policy, permissions policy) | Medium | `main.py` had only CORS + request logging | **FIXED** — `app/core/middleware.py` now sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store`, and a JSON-API CSP; tested |
| S2 | No request correlation IDs; logs could not be tied to a request | Medium | `app/core/logging.py`, `app/core/middleware.py` | **FIXED** — `app/core/request_context.py` ContextVar, safe allow-listed incoming `X-Request-ID`, echoed on responses, injected into every log line; tested |
| S3 | OpenAPI/Swagger exposed by default in production | Low | FastAPI defaults | **FIXED** — docs URLs are `None` unless `api_docs_enabled` and production debug (production validation forbids debug) |
| S4 | No rate limiting on expensive POST endpoints | Medium | No limiter found | **FIXED (partial)** — in-process fixed-window limiter for mutating requests, active by default in production, explicit opt-out available; single-instance only, edge limiting still required at scale |
| S5 | `/validation` and `/pilot` protected only client-side | Medium | `proxy.ts` matcher omitted both | **FIXED** — both added to protected prefixes and proxy matcher; routing assertions added |
| S6 | No browser security headers on frontend | Medium | `next.config.ts` had no `headers()` | **FIXED** — baseline header set and CSP with derived API origin; tested against service-role markers |
| S7 | Backend uses a privileged DB role; RLS is bypassed for all backend queries | High | `app/db/session.py` connects via `DATABASE_URL`; no `SET ROLE`; no `FORCE ROW LEVEL SECURITY` | **MITIGATED / ADVISORY** — authorization is enforced in FastAPI dependencies and geography-scoped SQL with automated tests. Changing the DB role model is a separate architectural change outside this phase. Residual risk: a missed dependency or SQL injection would expose rows a `SECURITY DEFINER` RLS policy would otherwise hide |
| S8 | `geographic_context_key` has no DB constraint or FK; arbitrary strings can be written | Medium | Migration `0023` | **MITIGATED / ADVISORY** — API rejects unregistered keys with 422; workspace filters fail closed; code-level registry is authoritative. DB-level FK deferred to a future additive migration |
| S9 | No dependency lock file and no SCA tooling; `python-multipart>=0.0.9` lower bound permits a historically vulnerable release | Medium | `backend/pyproject.toml` | **ADVISORY** — CI installs current allowed versions; no frozen resolution. Add a lock file and `pip-audit` gate in a follow-up |
| S10 | Two distinct `GovernanceError` classes, neither globally registered | Low | `governance/errors.py:6`, `governance/service.py:18` | **ADVISORY** — uncaught instances degrade to a safe generic 500 (no stack trace leaked). Consolidation deferred |
| S11 | Generic 500 handler and validation errors | Low | `core/exceptions.py` | **VERIFIED SAFE** — clients receive `{"error": {code, message}}`; stack traces remain server-side; new tests assert no traceback/file paths in responses |
| S12 | SSRF / redirect handling in acquisition | High | Phase 11/12 acquisition modules | **VERIFIED SAFE** — exact URL allowlist, no redirects, bounded bytes/records, content-type validation; Phase 12 tests prove arbitrary URLs rejected and failed acquisition cannot replace a valid snapshot |
| S13 | Service-role credential exposure in frontend | Critical if present | `frontend/.env.example`, `lib/supabase/config.ts` | **VERIFIED SAFE** — only `NEXT_PUBLIC_*` anon values; config actively rejects keys containing `service_role`; `.env.local` untracked; new CI security job rejects tracked env files and hard-coded service-role literals |
| S14 | JWT handling | High | `app/auth/jwt.py` | **VERIFIED SAFE** — asymmetric algorithms only, HS256 rejected, required `exp/iat/sub/aud/iss`, all verification flags on, token contents never logged |
| S15 | Error information leakage from health endpoints | Low | Health responses | **VERIFIED SAFE** — readiness/dependency endpoints expose only booleans, generic statuses and build version; no DSN, credentials, paths or stack traces |
| S16 | Personal data in logs | Medium | Logging middleware | **MITIGATED** — query strings and bodies excluded by design; request id is allow-listed to `[A-Za-z0-9._:-]{1,64}` to prevent log injection; log format contains no user fields |
| S17 | CORS wildcard with credentials | High | Config validator | **VERIFIED SAFE** — production rejects `*` with credentials; HTTPS required for Supabase URLs outside localhost |
| S18 | Insecure production defaults (`APP_ENV=development`) | Medium | `config.py` | **MITIGATED** — production validation rejects debug, empty CORS, missing DB/Supabase URL; reminder: deployments must set `APP_ENV=production` explicitly |

## 2. Geography-specific security review

- The client may select any context returned by the API, but the selected value
  is passed as a **server-side query filter**. The backend rejects unregistered
  keys with HTTP 422 and filters datasets, snapshots, ground truth, universes,
  infrastructure sources, assets and all aggregates. Tests prove one context
  never returns another context's rows, including the `UNKNOWN` bucket.
- Dhaka OSM snapshots serialize as `PUBLIC_OSM_RESEARCH` /
  `RESEARCH_CONTEXT_ONLY`; they cannot be represented as operational evidence
  or human-verified ground truth.
- Readiness payloads always set `pilot_activation_authorized: false` and never
  contain a model-activation switch.
- Database RLS policies `USING (true)` on `geographic_contexts` are read-only
  (`authenticated` has only `SELECT`); geography write authority stays with the
  backend/migrations.

## 3. Bangladesh privacy and legal review

Bangladesh-specific data protection obligations (including the Digital Security
Act and any applicable personal-data rules for field observations, location
data and reviewer identities) are **NOT_ASSESSED**. No legal compliance claim
is made. Qualified local legal review is a mandatory gate before any field
collection or pilot. Required controls for that review: consent capture,
location precision limits, reviewer pseudonymisation, retention limits,
access logging and a documented lawful basis.

## 4. Secrets scan

No secrets, private keys, credentials or database exports were found in changed
files. Only `.env.example` files are tracked. CI adds an automated guard for
tracked env files, private-key extensions and hard-coded service-role literals.

## 5. Residual risk summary

The highest remaining risk is S7 (privileged backend DB role bypassing RLS).
It is mitigated but not eliminated in this phase. The next material hardening
work should introduce a least-privilege database role with `SET ROLE` per
request, an additive FK/check constraint for `geographic_context_key`, and a
dependency lock with SCA in CI.
