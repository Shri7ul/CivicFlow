# Production Profile Provisioning Fix

Date: 2026-11-26
Scope: authenticated profile provisioning lifecycle on the live deployment
(Render backend `https://civicflow-8dol.onrender.com`, Vercel frontend
`https://civic-flow-lilac.vercel.app`, Supabase Auth/PostgreSQL).
Repository state before changes: `main` at `853141d`, worktree carried over
from the auth integration fix sprint.

No production user was created, no migration was run, no arbitrary database
write was performed, no auth gate was bypassed, and the Dhaka pilot remains
closed.

## Evidence gathered from the live deployment

| Probe | Result |
| --- | --- |
| Dashboard after email verification + login | `No CivicFlow profile exists for this identity. Call POST /api/v1/auth/provision.` |
| `POST /api/v1/auth/provision` (no token) | HTTP `500` |
| `POST /api/v1/auth/provision` (invalid token) | HTTP `500` |
| `GET /api/v1/auth/me` (no token) | HTTP `401 {"error":{"code":"authentication_failed",...}}` |

The `500` responses were not expected: the provisioning endpoint is designed
to return `401` for missing/invalid tokens (via `get_token_claims`) and `200`
for a valid new identity. The asymmetry between a correct `401` on the GET and
a `500` on the POST was the key diagnostic signal.

Local reproduction under a production-like configuration (`RATE_LIMIT_ENABLED=true`,
security headers on) produced:

```text
UnboundLocalError: cannot access local variable 'response' where it is not associated with a value
  File "app/core/middleware.py", line 123, in dispatch
```

## Root cause

`RequestLoggingMiddleware.dispatch` in `backend/app/core/middleware.py` only
assigned `response` inside the rate-limit **rejection** branch. The branch
structure was effectively:

```python
if rate_limited and method in MUTATING_METHODS and not excluded_path:
    if not limiter.allow(peer, started):
        response = Response(429, ...)
else:
    response = await call_next(request)
# response is read later for logging / header injection
```

When rate limiting is active (production) and the request method is mutating
(`POST`, `PUT`, `PATCH`, `DELETE`) and the request is **allowed** by the
limiter, neither branch executed `await call_next(...)`. `response` remained
unbound, and the later read raised `UnboundLocalError`, which FastAPI surfaced
as HTTP `500`.

Why the bug was invisible in ordinary local testing:

- The default test environment disables rate limiting, so mutating requests
  took the `else` branch and worked.
- `GET /api/v1/auth/me` is non-mutating, so it always reached the application
  and correctly returned `401` / `403`.
- Only the combination "rate limiting on + mutating method + allowed request"
  triggered the failure — exactly the production `POST /auth/provision` path.

A secondary inconsistency: `_HEALTH_PATHS` contained only `/health`, while the
real API path is `/api/v1/health`, so the rate-limit exclusion did not cover
the documented health endpoint.

## Lifecycle before the fix

1. Supabase Auth creates an identity (Auth user) on sign-up. No CivicFlow
   `Profile` row exists yet.
2. Email verification link redirects to the frontend callback; PKCE code is
   exchanged for a session.
3. `AuthProvider.syncSession` calls `GET /api/v1/auth/me` with the bearer
   token. `get_current_profile` finds no row with `Profile.id == verified.sub`
   and returns `403 {"code":"profile_required", "message":"No CivicFlow
   profile exists for this identity. Call POST /api/v1/auth/provision."}`.
4. The inline frontend handler attempted `POST /api/v1/auth/provision`, but the
   request hit the middleware defect and returned `500`; no profile row was
   created.
5. Every session restoration repeated steps 3–4. The dashboard could never
   obtain a profile, showing the provisioning message indefinitely.

## Lifecycle after the fix

1. Supabase Auth identity and callback/session are unchanged.
2. `AuthProvider.syncSession` now delegates to
   `loadOrProvisionProfile(session.access_token)` in
   `frontend/src/lib/api/auth.ts`.
3. `loadOrProvisionProfile` first calls `GET /api/v1/auth/me`:
   - existing profile -> returns it (no provisioning call);
   - `403` with `code === "profile_required"` -> calls
     `POST /api/v1/auth/provision` with body `{}`;
   - any other error (`401`, other `403`, `5xx`, network, invalid response) is
     rethrown unchanged and classified by `profileLoadMessage`.
4. With rate limiting active, the middleware now calls `await call_next(request)`
   for allowed mutating requests, so `POST /auth/provision` reaches the
   endpoint. `provision_profile` creates a `Profile` with `id = verified.subject`,
   role `CITIZEN`, using the JWT subject/email only, and returns `200`.
5. The next `GET /auth/me` returns the profile and the dashboard renders
   normally. Subsequent reloads reuse the profile without reprovisioning.

### Security and idempotency properties preserved

- Identity comes only from the verified JWT (`sub`, `email`); no client-supplied
  identity is trusted.
- The browser payload is `{}` (optionally `full_name`); it never carries a
  `role`. The server hardcodes `Role.CITIZEN`.
- Provisioning is idempotent: `Profile.id` is the primary key, and a concurrent
  insert causing `IntegrityError` is rolled back and resolved by re-reading the
  existing row.
- An inactive account returns `403 account_inactive` and is never reprovisioned
  into an active state.
- `401` (missing/invalid/expired token) and non-`profile_required` `403` never
  trigger provisioning.
- `5xx` / network failures surface as structured errors; there is no silent
  fallback that would hide a real backend failure.

## Files changed

| File | Change |
| --- | --- |
| `backend/app/core/middleware.py` | Initialize `response = None`; call `await call_next(request)` when no rate-limit rejection was produced; add `/api/v1/health` to `_HEALTH_PATHS`. |
| `backend/tests/test_provisioning_middleware.py` | New regression suite exercising allowed mutating requests, invalid tokens, new-user provisioning, idempotency, 429 throttling, and structured DB failures with rate limiting enabled. |
| `frontend/src/lib/api/auth.ts` | Add `loadOrProvisionProfile(token)` centralizing the GET-then-conditional-POST lifecycle; import `ApiError`. |
| `frontend/src/components/auth/auth-provider.tsx` | Replace inline provisioning logic with `loadOrProvisionProfile`. |
| `frontend/src/lib/api/auth-lifecycle.test.ts` | New deterministic lifecycle tests (reuse, provision-on-missing, reload after provision, 401, non-profile 403, 500, network, no privileged role in payload). |
| `docs/deployment/PRODUCTION_PROFILE_PROVISIONING_FIX.md` | This document. |

## Verification performed

All checks were run locally against the checked-out repository; no production
data was written.

| Check | Result |
| --- | --- |
| `backend: python -m pytest` | **316 passed**, 2 warnings in 39.09s |
| `backend: pytest tests/test_provisioning_middleware.py` (focused) | **6 passed** |
| Local production-like reproduction: `POST /auth/provision` no token | `401 authentication_failed` (was `500`) |
| Local production-like reproduction: `POST /auth/provision` invalid token | `401 authentication_failed` (was `500`) |
| Local production-like reproduction: `GET /auth/me` no token | `401 authentication_failed` |
| `frontend: npm run typecheck` | passed |
| `frontend: npm run lint` | passed |
| `frontend: npm test` (Vitest) | **35 files, 132 tests passed** |
| `frontend: npm run build` | passed |

The two pytest warnings are pre-existing dependency deprecations
(`starlette.testclient`/httpx) and a harmless SQLite reflection warning in the
migration test; neither is related to this change.

## Production deployment steps (operator action required)

The agent did not deploy to Render or Vercel (no platform access was
available). The fixes are code-only and require a normal redeploy:

1. **Render backend** — redeploy the web service from `main`. No migration is
   needed (no schema change). Confirm build uses `backend/requirements.txt` and
   Python 3.11 per `render.yaml`.
2. **Render environment** — verify `CORS_ORIGINS` includes
   `https://civic-flow-lilac.vercel.app`, `SUPABASE_URL` is correct,
   `SUPABASE_JWT_AUDIENCE=authenticated`, and JWKS is derivable or set. Record
   the current `RATE_LIMIT_ENABLED` / request-per-minute values.
3. **Vercel frontend** — redeploy from `main` with `NEXT_PUBLIC_SITE_URL=https://civic-flow-lilac.vercel.app`
   and `NEXT_PUBLIC_API_BASE_URL=https://civicflow-8dol.onrender.com`.
4. **Supabase Auth** — confirm the Site URL and redirect allowlist contain
   `https://civic-flow-lilac.vercel.app/auth/callback` (see
   `PRODUCTION_AUTH_INTEGRATION_FIX.md`).
5. **Smoke check** — run `backend/scripts/production_smoke_test.py` against the
   redeployed backend, then perform the manual verification below with a real
   verified account.

## Manual verification procedure (with a real verified user)

1. From a clean browser session, sign up / log in with a real Supabase account
   and complete email verification.
2. Confirm the verification redirect lands on
   `https://civic-flow-lilac.vercel.app/auth/callback?code=...` and establishes
   a session (no `localhost:3000` redirect).
3. Open the dashboard. It should load the user's profile without the
   `No CivicFlow profile exists` message.
4. In the browser Network tab:
   - a new identity should show exactly one `POST /api/v1/auth/provision`
     returning `200` with `"role":"CITIZEN"`, followed by `GET /api/v1/auth/me`
     returning `200`;
   - an existing identity should show only `GET /api/v1/auth/me` (`200`) and
     **no** provisioning call.
5. Reload the page twice: the profile persists and no further provisioning
   requests occur.
6. Repeat with a second distinct identity to confirm no cross-user data leak.
7. Check Render logs: no `UnboundLocalError` and no `500` for
   `POST /api/v1/auth/provision`.

## Remaining blockers / limitations

- No browser end-to-end verification with a real production Supabase account
  was performed by the agent: no credentials or authorization were provided,
  and no test/production user was created.
- No Render or Vercel redeploy was performed by the agent: no CLI/connector/token
  access was available. Post-fix live confirmation therefore depends on the
  operator steps above.
- The pre-fix `500` evidence is from the live deployment; the `401`/`200`
  confirmation is from local production-like reproduction, not from a live
  redeployed service.
- CORS allowlisting and Supabase redirect settings must be confirmed in the
  respective dashboards; they cannot be verified solely from the repository.
- The Dhaka controlled pilot remains inactive and all models remain
  `RESEARCH_ONLY`. This change does not affect pilot gates or activation state.
