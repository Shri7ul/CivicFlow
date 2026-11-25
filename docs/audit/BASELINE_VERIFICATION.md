# CivicFlow — Baseline Verification

Date: 2026-11-26
Purpose: record the *actual* state of the repository before any recovery changes, without hiding pre-existing failures.

## 1. Git baseline

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD before changes | `bd926ac262cb28e874f0fcdb6aef75ce7dee8279` |
| Subject | `fix(auth): repair profile provisioning lifecycle under rate limiting` |
| Upstream | `origin/main` |
| Sync state | `## main...origin/main` — ahead 0, behind 0 |
| Worktree | clean (no modified or untracked files) |
| Recent history | `bd926ac` → `853141d` (auth redirect/profile fix) → `811047b` (Render prep) |

## 2. Command results (executed, not assumed)

All commands were run twice independently (sprint lead and read-only test audit) with identical outcomes.

| Command | Result |
| --- | --- |
| `cd backend && ./.venv/Scripts/python.exe -m pytest` | **316 passed**, 2 warnings, ~35–39s, exit 0 |
| `cd frontend && npm test` | **35 test files, 132 tests passed**, ~0.6–0.7s, exit 0 |
| `cd frontend && npm run typecheck` | clean, exit 0 |
| `cd frontend && npm run lint` | clean, exit 0 |
| `cd frontend && npm run build` | success (Next.js 16.4.6, static/partial-prerender routes emitted), exit 0 |
| `backend/.pytest_cache/v/cache/lastfailed` | `{}` — no cached prior failures |

### Pre-existing warnings (not introduced by this sprint)

1. `StarletteDeprecationWarning` — `starlette.testclient` with httpx is deprecated; upstream dependency issue.
2. `SAWarning` — SQLite reflection skips expression-based index `uq_departments_name_lower` in `tests/db/test_migrations.py::test_sqlite_upgrade_and_downgrade`; harmless for the in-memory SQLite fixture.

### Pre-existing failures

**None reproducible.** The suite is green at baseline. This is recorded explicitly so later failures can be attributed correctly.

## 3. Baseline defects reproduced by inspection

These are not test failures; they are product defects confirmed in source. Full detail is in `FULL_PROJECT_AUDIT.md`.

| Defect | Evidence |
| --- | --- |
| Incident form submits hard-coded Dhaka coordinates | `frontend/src/app/incidents/new/report-incident-form.tsx:34-35,87-88` |
| Geolocation blocked by Permissions-Policy | `frontend/next.config.ts:47` vs `report-incident-form.tsx:41-64`, `incident-map.tsx:465-498` |
| Map glyph fetches blocked by CSP `connect-src` | `frontend/src/lib/map.ts:22`, `frontend/next.config.ts:21-26,33` |
| Nav shows all staff modules to citizens | `frontend/src/components/auth/auth-nav.tsx:24-95` |
| Generic API 401/403 not handled; no error boundary | `auth-provider.tsx:216-226`; no `error.tsx`/`not-found.tsx` in `frontend/src/app` |
| Password recovery absent | no `resetPasswordForEmail` / reset page / reset callback in source |
| `/risk/cells` has no response model | `backend/app/api/v1/endpoints/risk.py:204-207` |
| Observation submission body discarded | `backend/app/api/v1/endpoints/phase14.py:229` (`del payload`) |
| Validation correlation/decision errors become 500 | `backend/app/api/v1/endpoints/validation.py:278-299` |
| Phase 10 docstring contradicts actual permissions | `phase10.py:3-4` vs `:394-399`,`:451-457`,`:555-561` |
| Migration filename/revision mismatch | `backend/alembic/versions/0015_ingested_record_provenance.py:16` |
| Stale deployment docs claim no live deployment | `docs/deployment/PRODUCTION_DEPLOYMENT_{AUDIT,REPORT,VERIFICATION}.md` |

## 4. Live baseline probes (read-only)

| Target | Result |
| --- | --- |
| `https://civicflow-8dol.onrender.com/api/v1/health` | 200, `status: healthy`, `environment: production` |
| `https://civicflow-8dol.onrender.com/api/v1/health/dependencies` | 200, `database: reachable`, auth configured, build `0.11.0` |
| `https://civicflow-8dol.onrender.com/docs` | 404 (docs disabled in production) |
| `https://civic-flow-lilac.vercel.app` | 200, real rendered page with CSP/HSTS headers |

These probes establish that deployment exists. They do **not** establish that a verified user can complete the browser auth lifecycle — no production credentials were used.

## 5. Configuration baseline

| Item | State |
| --- | --- |
| `render.yaml` | `plan: free`, `rootDir: backend`, requirements install, uvicorn start, `healthCheckPath: /api/v1/health`, Python 3.11, secrets `sync: false` |
| `frontend/vercel.json` | Next.js framework, `npm ci`, `npm run build`; no env vars declared |
| `frontend/next.config.ts` | CSP + security headers live on all paths; `connect-src` derived at build time from `NEXT_PUBLIC_API_BASE_URL` |
| `.github/workflows/verify.yml` | pytest + single Alembic head + typecheck + lint + Vitest + production build + secret scan |
| Tracked secrets | none — only `.env.example` files; `.gitignore` ignores `.env*`; local `.env`/`.env.local` exist but are untracked |
| Alembic | 24 migrations, single head `0024_phase14_pilot` |
| Live DB head (from existing docs, not queried) | `0022_snapshot_provenance`; `0023`/`0024` pending, no authorized migration |

## 6. Baseline conclusion

The repository is in a **green, clean, synced** state with a fully passing test suite. Therefore any regression introduced by this recovery sprint is attributable to its own changes. The problems are product/UX/contract defects and stale documentation, not a broken build or failing tests. That distinction drives the repair strategy: targeted fixes plus tests, not a rewrite.
