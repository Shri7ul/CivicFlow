# Phase 13 — Production Hardening & Dhaka Evidence Readiness Report

Date: 2026-11-25
Status label rule: each outcome is labelled with exactly one of
**IMPLEMENTED**, **AUTOMATED-TESTED**, **LIVE-VERIFIED**,
**REAL-DATA-VERIFIED**, **HUMAN-VERIFIED**, **SIMULATED**, **BLOCKED** or
**NOT_ASSESSED**. One label never implies another.

---

## 1. Phase 13 summary

Phase 13 strengthened the running application and its verification pipeline
without activating any civic action. A full production security audit was
performed; confirmed gaps (security headers, request correlation, production
docs exposure, unthrottled mutating requests, client-only route guards) were
fixed with tests. Backend and frontend hardening, dependency-aware health
endpoints, an adversarial geographic-isolation matrix, readiness-gate
integrity tests, and a CI verification workflow were implemented. Migration
`0023_phase12_geography` was reviewed and inspected read-only against the live
database; it was **not** applied. Backup/recovery, monitoring and Dhaka
evidence readiness were documented honestly.

No model, pilot, alert, dispatch, resource allocation or public deployment was
activated. No historical NYC dataset, hash, provenance value or experiment was
modified.

## 2. Repository baseline

- Branch `main`, clean tree, HEAD `1c3879e`, in sync with `origin/main` before work.
- Backend: FastAPI/Pydantic 2/SQLAlchemy 2/Alembic, 16 routers, asymmetric JWT
  ES256/RS256, RBAC (`CITIZEN`/`WORKER`/`ADMIN`), RLS on 57 live public tables.
- Frontend: Next.js **16.4.6** (brief assumed 14/15), React 19.3, Vitest 5,
  15 pages; route protection via `src/proxy.ts`.
- CI/deployment/backup/monitoring: none found at baseline.
- Baseline tests: backend 251 passed, frontend 94 passed.
- Live DB head: `0022_snapshot_provenance`; `geographic_contexts` absent.
- Full detail: `docs/development/PHASE13_BASELINE.md` (**LIVE-VERIFIED**, read-only).

## 3. Changes implemented

### Backend (**IMPLEMENTED / AUTOMATED-TESTED**)

| Change | Location |
| --- | --- |
| Request correlation IDs with safe incoming-header allow-list | `app/core/request_context.py`, `app/core/middleware.py` |
| Request IDs in every log line, no query/body logging | `app/core/logging.py` |
| Baseline security headers + JSON-API CSP | `app/core/middleware.py` |
| In-process fixed-window limiter for mutating requests (production default) | `app/core/middleware.py`, `app/core/config.py` |
| Docs/OpenAPI disabled in production by default | `app/core/config.py`, `app/main.py` |
| Dependency-aware readiness and non-sensitive dependency endpoints | `app/api/v1/endpoints/health.py`, `app/schemas/health.py` |
| Engine and limiter cleanup on graceful shutdown | `app/main.py` |
| Production hardening settings with explicit override semantics | `app/core/config.py` |

### Frontend (**IMPLEMENTED / AUTOMATED-TESTED**)

| Change | Location |
| --- | --- |
| Security headers and derived-origin CSP | `next.config.ts` |
| `/validation` and `/pilot` added to optimistic proxy protection | `src/proxy.ts`, `src/lib/auth/routing.ts` |
| Security-header and no-service-role tests | `src/config/security.test.ts` |
| Current phase label | `src/config/app.ts` |

### CI and repository safety (**IMPLEMENTED**, not live-verified)

`.github/workflows/verify.yml` runs backend tests, a single-head Alembic check,
frontend typecheck/lint/tests/build, and repository safety checks on push,
pull request and manual dispatch. It never deploys and references no secrets.
Root `.gitignore` now excludes local database/dump exports.

### Tests added

- `backend/tests/test_phase13_hardening.py` — 18 tests covering request IDs,
  security headers, no stack-trace leakage, readiness gating, dependency
  endpoint shape, production config, rate limiting, a 3-context geographic
  isolation matrix, client-scope widening, readiness-gate integrity and
  migration regression guards (**AUTOMATED-TESTED**).
- `frontend/src/config/security.test.ts` — header/CSP and credential checks.

All fixtures are synthetic and are never counted as operational evidence
(**SIMULATED**).

## 4. Security findings

Full audit: `docs/security/PHASE13_SECURITY_AUDIT.md`.

Fixed with tests: missing security headers (backend + frontend), no request
correlation, production docs exposure, absent rate limiting, client-only guards
for `/validation` and `/pilot`.

Verified safe: JWT verification (asymmetric only, HS256 rejected), acquisition
allowlist/no-redirect/byte caps, frontend anon-key-only configuration with
active service-role rejection, generic 500 handler with no stack traces, CORS
wildcard-with-credentials rejection in production.

Advisory / mitigated: backend uses a privileged DB role so RLS is not the
backend authorization boundary (**MITIGATED** by app-layer RBAC and geography
scoping); `geographic_context_key` has no DB constraint/FK; no dependency lock
or SCA; two inconsistent `GovernanceError` classes; `APP_ENV` defaults to
`development` so deployments must set production explicitly.

Bangladesh privacy/legal compliance is **NOT_ASSESSED** — no compliance claim is
made; qualified local legal review is a mandatory pre-field gate.

## 5. Security fixes

See §3 and the audit document. No security control was weakened to pass tests;
no insecure fallback credential was introduced; no service-role key exists in
frontend code. A secrets scan over changed files found no secrets, keys or
database exports (**AUTOMATED-TESTED** locally).

## 6. Geographic isolation findings

Adversarial matrix executed over `US-NYC`, `BD-DHAKA` and `UNKNOWN`:

- Each context returns only its own rows; `UNKNOWN` returns none (**AUTOMATED-TESTED**).
- A client-supplied Dhaka filter over a store containing only NYC rows returns
  an empty Dhaka-scoped result, not NYC rows (**AUTOMATED-TESTED**).
- Unregistered context keys are rejected with HTTP 422.
- Dhaka OSM snapshots serialize as `PUBLIC_OSM_RESEARCH` /
  `RESEARCH_CONTEXT_ONLY` and cannot become operational evidence.
- NYC holdouts and bridge overlap are excluded from Dhaka-scoped workspaces.
- Readiness never authorizes pilot or model activation.
- `geographic_contexts` has RLS with read-only `authenticated` grant.

## 7. Migration 0023 status

- Local head: `0023_phase12_geography`; single head confirmed by `alembic heads`.
- Offline upgrade/downgrade and column-parity tests pass (**AUTOMATED-TESTED**).
- Live head: `0022_snapshot_provenance` (**LIVE-VERIFIED**, read-only).
- Schema compatibility verified: all referenced columns exist; RLS enabled on
  all five tagged tables; 6 NYC datasets and 3 snapshots preserved.
- Additive: one new table, one new column + index per tagged table, conservative
  backfill of only the new column; no hash, provenance, raw/normalized content
  or history rewritten.
- **Advisory defect found**: offline `--sql` rendering emits `INSERT ... VALUES
  (NULL, ...)` for the two context seed rows because the Python seed loop does
  not execute in offline mode. Offline SQL must be used for review only;
  deployment must use online `alembic upgrade head`.
- Deployment: **BLOCKED** — no verified backup and no explicit deployment
  authorization. Migration was not applied live.

## 8. Production deployment status

**BLOCKED**. No deployment platform configuration exists in the repository; no
production deployment was attempted. CI is verification-only. Health probes are
documented for a future platform (`/health` liveness, `/health/ready`
readiness) but are not wired anywhere.

## 9. Backup/recovery status

**Unavailable / NOT_ASSESSED**. No backup configuration, retention policy, PITR
verification, restore test or deployment rollback exists in repository
evidence. Provider-managed Supabase backups were not inspected. Detail:
`docs/operations/PHASE13_BACKUP_RECOVERY.md`.

## 10. Monitoring status

**IMPLEMENTED / AUTOMATED-TESTED** locally; **NOT LIVE-VERIFIED** in production.
Request IDs, request timing, liveness/readiness/dependency endpoints, build
version and baseline headers are in place. No external monitoring vendor or
credential was added. Detail: `docs/operations/PHASE13_MONITORING.md`.

## 11. Dhaka evidence readiness

**IMPLEMENTED (capability) / BLOCKED (authoritative data)**. The acquisition
pipeline can safely ingest future sources with allowlisting, provenance,
geographic tagging and research/operational separation. Only one source is
actually integrated: the bounded central-Dhaka OSM research cell. No official
complaint, boundary, infrastructure or weather source is integrated; no Dhaka
ground truth or correlation labels exist. Detail:
`docs/dhaka/DHAKA_EVIDENCE_READINESS_PHASE13.md`.

The Phase 12 real snapshot remains unchanged: 552 raw elements → 511 normalized
features, 41 rejected, raw 447,201 bytes, raw SHA-256 `928c6d91…281d73`,
normalized SHA-256 `7b49ff62…f50453`, OSM base `2026-11-24T23:13:20Z`
(**REAL-DATA-VERIFIED** in Phase 12; not re-acquired in Phase 13).

## 12. Pilot readiness

Dhaka readiness remains **NOT_READY** with `pilot_activation_authorized=false`.
Mandatory blockers persist: official boundary, approved pilot area,
authoritative sources, ground truth, correlation labels, validation/baseline,
stakeholder approval, reviewer training, legal review, escalation, rollback and
verified backups. Phase 13 did not manufacture readiness to satisfy completion.

## 13. Test results

| Check | Result |
| --- | --- |
| Backend suite | **269 collected / 269 passed / 0 failed**, exit 0 (**AUTOMATED-TESTED**) |
| — Phase 12 tests | 19 passed |
| — Phase 13 tests | 18 new passed |
| Frontend tests | **30 files / 96 tests passed** |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Migration tests (incl. 0023 up/down, column parity, single head) | PASS |
| YAML validation of CI workflow | PASS |
| Secret scan of changed files | Clean |

A sandbox atexit shim warning on pytest temp cleanup was observed; it did not
affect results. Build required unsetting two sandbox shim variables for Next's
gitignored cache cleanup; no code or data impact.

## 14. Build results

Production build passed with Next.js 16.4.6 (Turbopack), all 15 routes
prerendered or partially prerendered, no errors (**AUTOMATED-TESTED**).

## 15. Live verification results

Read-only only (**LIVE-VERIFIED**): DB reachable, head `0022`, 57 tables, RLS on
evidence/datasets/GT/universes/pilots, 6 `nyc311-*` datasets, 3 snapshots, 0
pilots, schema compatible with `0023`. No writes, migrations, resets or
destructive operations. The live production HTTP surface and the CI workflow on
GitHub were **NOT_ASSESSED** / **NOT LIVE-VERIFIED**.

## 16. Remaining blockers

1. Verified backup, retention policy and restore drill before any live migration.
2. Deployment authorization and platform configuration for `0023` (and online-only application).
3. Authoritative DNCC/DSCC/RAJUK boundaries and non-OSM Dhaka sources.
4. Human-verified field ground truth and complete correlation reference universe.
5. Dhaka external validation against a recomputed baseline.
6. Stakeholder agreement, reviewer training, legal/privacy review, escalation and rollback drills.
7. Least-privilege DB role, `geographic_context_key` FK/check constraint, dependency lock + SCA, edge rate limiting.

## 17. Files modified / created

Backend: `app/core/request_context.py` (new), `app/core/middleware.py`,
`app/core/logging.py`, `app/core/config.py`, `app/main.py`,
`app/schemas/health.py`, `app/api/v1/endpoints/health.py`,
`tests/test_phase13_hardening.py` (new).
Frontend: `next.config.ts`, `src/proxy.ts`, `src/lib/auth/routing.ts`,
`src/lib/auth/routing.test.ts`, `src/config/app.ts`,
`src/config/security.test.ts` (new).
CI/config: `.github/workflows/verify.yml` (new), `.gitignore`.
Docs: `PHASE13_REPORT.md`, `PHASE13_BASELINE.md`, `PHASE13_SECURITY_AUDIT.md`,
`PHASE13_BACKUP_RECOVERY.md`, `PHASE13_MONITORING.md`,
`DHAKA_EVIDENCE_READINESS_PHASE13.md`, `docs/PROGRESS.md`.

## 18. Git commit hash

Recorded after the Phase 13 commit (see the final Git-state update appended to
this report).

## 19. Push status

Recorded after the Phase 13 push (see the final Git-state update appended to
this report).

## 20. Final verdict

- **IMPLEMENTED**: backend/frontend hardening, request IDs, security headers,
  health/readiness endpoints, production config rules, CI workflow, six Phase 13
  documents.
- **AUTOMATED-TESTED**: 269 backend + 96 frontend tests, migration checks,
  typecheck, lint, production build, secret scan, CI YAML validation.
- **LIVE-VERIFIED**: read-only Phase 11 database baseline only.
- **REAL-DATA-VERIFIED**: no new Phase 13 acquisition; Phase 12 OSM artifact unchanged.
- **HUMAN-VERIFIED**: nothing in Phase 13.
- **SIMULATED**: deterministic test fixtures only; never operational evidence.
- **BLOCKED**: live migration `0023`, production deployment, authoritative Dhaka
  sources, ground truth, correlation, validation, pilot and model activation.
- **NOT_ASSESSED**: provider backups/PITR, production HTTP surface, remote CI
  run, Bangladesh legal compliance, reviewer training, stakeholders.

**CivicFlow is NOT ready for a Dhaka controlled pilot.** Phase 13 completed its
hardening and documentation scope; it did not authorize or perform any pilot,
model, deployment or automated civic action.
