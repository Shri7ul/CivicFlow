# Production Auth & Integration Fix

Date: 2026-11-26
Scope: production auth redirect, profile loading, API error classification,
frontend-to-backend CORS integration. Repository state before changes: `main`
at `811047b`, clean and synced with `origin/main`.

## Evidence gathered from the live deployment

| Probe | Result |
| --- | --- |
| `GET https://civicflow-8dol.onrender.com/api/v1/health` | `200 {"status":"healthy",...,"environment":"development"}` |
| `GET /api/v1/auth/me` with `Origin: https://civic-flow-lilac.vercel.app`, no token | `401 {"error":{"code":"authentication_failed",...}}`; `access-control-allow-credentials: true` but **no** `access-control-allow-origin` |
| `OPTIONS /api/v1/auth/me` with the same origin, `Access-Control-Request-Headers: authorization,content-type` | **400 `Disallowed CORS origin`**, no `access-control-allow-origin` |
| `GET /docs`, `GET /openapi.json` | `200` (API docs exposed in production) |
| `GET /api/v1/health/dependencies` | `200 operational`, DB reachable, `auth_verification_configured: true` |

No authenticated live request was made: no valid production token was
available and no account was created.

## Root cause — Bug 1: profile loading failure

The error text "Unable to reach the CivicFlow API. Check that the backend is
running." is produced by `apiFetch` in `frontend/src/lib/api/client.ts` when
`fetch()` rejects at the browser layer. It is **not** evidence that the backend
is down.

The profile request `GET /api/v1/auth/me` includes an `Authorization` header,
so the browser first performs a CORS preflight (`OPTIONS`). The live backend
answers that preflight with **400 "Disallowed CORS origin"** because Render's
`CORS_ORIGINS` does not include `https://civic-flow-lilac.vercel.app`. The
browser therefore never sends the actual GET, `fetch()` rejects, and the UI
renders the network-unreachable message. The unauthenticated health GET is a
"simple" request with no preflight, which is why it returns 200 and appears to
contradict the failure.

Contributing code defects (now fixed):

- A `200` response with an unparsable body was caught by the generic `catch`
  in `apiFetch` and mislabeled `network_error`.
- `loginError()` returned raw backend messages without classifying 401, 403
  or 5xx, so an HTTP authentication/authorization failure could be presented
  as a generic profile/network problem.
- `refreshProfile()` did not clear session state on 401.

The production remediation itself is a **Render dashboard change** (section
"Render changes required"), because CORS is read from the environment at app
startup. Changing repository code alone cannot fix the live preflight.

## Root cause — Bug 2: verification redirects to localhost

`signUp()` passed `emailRedirectTo` built from `window.location.origin +
"/auth/callback"`. There was no explicit site-origin environment variable, and
the Supabase project's Site URL is the default localhost value: the observed
email link redirected to `http://localhost:3000/?code=...` (root path, not the
app callback path), which is consistent with Supabase falling back to its
configured Site URL because the supplied redirect was not allowlisted.

This is primarily a **Supabase Auth dashboard configuration issue**. The code
changes make the intended redirect explicit and testable via
`NEXT_PUBLIC_SITE_URL`, preserving dev localhost behavior and avoiding a
hardcoded production hostname in source. The dashboard change in the section
below is still mandatory; no repository change can alter Supabase project
settings. The public `GET /auth/v1/settings` endpoint did not expose
`site_url`, so the dashboard value could not be verified directly from here.

## Files changed

**Application**

- `frontend/src/lib/auth/redirect.ts` (new) — `getConfiguredSiteOrigin()`,
  `getSiteOrigin()`, `getEmailRedirectTo()`, `isLocalRedirect()`.
- `frontend/src/lib/auth/session.ts` (new) — `requireAccessToken()`,
  `authorizationHeader()`.
- `frontend/src/lib/auth/callback.ts` (new) — `readCallbackParameters()` for
  PKCE `code`, provider error and safe `next` path; never embeds the code in
  messages.
- `frontend/src/lib/api/errors.ts` (new) — `profileLoadMessage()` classification.
- `frontend/src/lib/api/client.ts` — malformed successful JSON now yields
  `invalid_response` instead of `network_error`.
- `frontend/src/components/auth/auth-provider.tsx` — uses explicit
  `getEmailRedirectTo()`, `requireAccessToken()`, and classified error
  messages; `refreshProfile()` clears the session on 401.
- `frontend/src/app/auth/callback/page.tsx` — uses `readCallbackParameters()`.
- `frontend/.env.example` — documents `NEXT_PUBLIC_SITE_URL`.

**Tests**

- `frontend/src/lib/auth/redirect.test.ts` (6 tests)
- `frontend/src/lib/auth/callback.test.ts` (5 tests)
- `frontend/src/lib/auth/session.test.ts` (4 tests)
- `frontend/src/lib/api/errors.test.ts` (11 tests)
- `frontend/src/lib/api/health.test.ts` (2 added tests)

## Fix implementation

1. **Redirect origin**: `NEXT_PUBLIC_SITE_URL` is preferred; invalid values
   (paths, queries, non-HTTP schemes) are ignored. Next preference is
   `window.location.origin` (dev), then `http://localhost:3000`.
   `getEmailRedirectTo()` always appends `/auth/callback`. No production
   hostname is hardcoded in application source.
2. **Token handling**: a single `requireAccessToken()` produces a structured
   401 when the token is missing/blank, used by `apiRequest`, `uploadRequest`
   and `refreshProfile`.
3. **Error separation**: 401 → expired session, 403 → permission denied,
   5xx → temporary API failure, `network_error`/`request_timeout` → backend
   unreachable, `invalid_response` → malformed response. A 401/403 can no
   longer be rendered as "backend unreachable".
4. **Callback**: PKCE code and error description are parsed in one pure
   helper; `safeNextPath()` prevents open redirects; the code is not logged or
   included in error text.

## Tests performed — actual results

| Command | Result |
| --- | --- |
| `npm run typecheck` | passed |
| `npm run lint` | passed |
| `npm test` | **34 files, 124 tests passed** |
| `npm run build` | passed |
| Backend `python -m pytest` | **310 passed**, 2 warnings |

Covered requirements: registration redirect selection, production and dev
callback URLs, callback code handling, profile request with valid token,
missing/expired token, HTTP 401/403/5xx, network failure, malformed response,
health 200 and health failure, and a regression test asserting that a
configured production origin never yields a localhost redirect.

Live HTTP verification (CORS preflight, health, auth rejection, docs exposure)
was executed with `curl` against the deployed backend; browser-based
verification was **not** performed and is not claimed.

## Supabase Auth settings required (manual)

In Supabase dashboard → Authentication → URL Configuration:

- **Site URL**: `https://civic-flow-lilac.vercel.app`
- **Redirect URLs** (allowlist):
  - `https://civic-flow-lilac.vercel.app/auth/callback`
  - `http://localhost:3000/auth/callback` (development)
- Keep email confirmation enabled for sign-up. supabase-js v2 uses the PKCE
  flow; the `/auth/callback` route exchanges the `code` for a session.
- Do not add wildcard redirect URLs. The app sends only the configured origin
  plus `/auth/callback`.

## Vercel environment variables required (manual)

- `NEXT_PUBLIC_SITE_URL=https://civic-flow-lilac.vercel.app`
- `NEXT_PUBLIC_API_BASE_URL=https://civicflow-8dol.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (project values)

`NEXT_PUBLIC_*` values are embedded at build time: trigger a fresh Vercel
deployment after changing them.

## Render environment / CORS changes required (manual)

In Render → `civicflow-api` → Environment, set:

- `CORS_ORIGINS=https://civic-flow-lilac.vercel.app` (exact origin, no `*`,
  no trailing slash)
- `CORS_ALLOW_CREDENTIALS=true`
- `APP_ENV=production` and `DEBUG=false` — the live health endpoint currently
  reports `environment: "development"` and `/docs` and `/openapi.json` return
  200, so production hardening is not active.
- Confirm `DATABASE_URL` and `SUPABASE_URL` remain set.

Save and redeploy; CORS and docs gating are read at application startup.

## Remaining manual verification steps

1. After Render redeploy, repeat the preflight:
   `curl -i -X OPTIONS -H 'Origin: https://civic-flow-lilac.vercel.app' -H
   'Access-Control-Request-Method: GET' -H 'Access-Control-Request-Headers:
   authorization,content-type' https://civicflow-8dol.onrender.com/api/v1/auth/me`
   Expect a success status and `access-control-allow-origin:
   https://civic-flow-lilac.vercel.app`.
2. Confirm `/docs` and `/openapi.json` return 404 after `APP_ENV=production`.
3. Register a new test user on the Vercel site; confirm the verification email
   link opens `https://civic-flow-lilac.vercel.app/auth/callback?code=...`.
4. Confirm the callback redirects to `/dashboard`, the session is established,
   and the profile loads (no "Unable to reach" error).
5. Sign out and sign in again; verify protected routes, an unauthorized API
   request (401), and role-restricted access (403) behave distinctly.
6. Check the browser console for CORS or CSP errors.

## Known limitations

- No Render, Vercel or Supabase dashboard access was available; none of the
  required platform settings were applied by this sprint.
- No authenticated live end-to-end test was possible without a real user
  token; no accounts or tokens were created.
- The Supabase Site URL could not be read from the public settings endpoint;
  the localhost redirect remains the evidence for it.
- Browser console verification was not performed; only HTTP-level checks were
  run against the live backend.
- Rate limiting remains in-process per instance; Render Free cold starts can
  add latency to the first request after idle.
- No database migration, data write, or pilot activation occurred.
