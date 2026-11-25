# Phase 13 Baseline — Repository and Deployment

Date: 2026-11-25
Status: **IMPLEMENTED / LIVE-VERIFIED (read-only)**

This document records the repository state observed before Phase 13 changes. It
does not rewrite or supersede Phase 8–12 reports.

## 1. Git and repository

| Item | Observed value |
| --- | --- |
| Branch | `main` |
| HEAD before Phase 13 | `1c3879e docs(civicflow): record phase 12 verification and push state` |
| Previous commits | `7d402ce` (Phase 12 implementation), `a3babc9` (Phase 11 hardening) |
| Working tree before work | Clean |
| Remote | `origin` → `https://github.com/Shri7ul/CivicFlow.git` |
| Upstream relationship | `origin/main...HEAD` = `0 0` (in sync) |
| Phase 12 state | Implemented, automated-tested, committed and pushed |

## 2. Architecture observed

| Layer | Observed |
| --- | --- |
| Backend | FastAPI + Pydantic 2 + SQLAlchemy 2.x + Alembic, modular monolith, 16 routers under `/api/v1` |
| Frontend | Next.js **16.4.6** (not 14/15), React 19.3, Tailwind 4, Vitest 5, 15 pages |
| Database | Supabase PostgreSQL/PostGIS; 57 public tables at live head `0022` |
| Auth | Supabase Auth, asymmetric JWT (RS256/ES256), RBAC (`CITIZEN`/`WORKER`/`ADMIN`), RLS on most domain tables |
| Migration chain | Linear `0001` → `0023_phase12_geography`, single head |
| Deployment | **No** `vercel.json`, `render.yaml`, Dockerfile, compose file or platform config found |
| CI | **No** CI configuration found; only local `scripts/verify.ps1` |
| Backup / restore | **No** repository evidence of backup configuration, scripts, retention or restore test |
| Monitoring | Plain-text stdlib logging, two health endpoints, no external vendor, no request IDs |

## 3. Tests before Phase 13

| Suite | Result |
| --- | --- |
| Backend `pytest -q` | 251 passed, 0 failed (exit 0) |
| Frontend `npm test` | 29 files / 94 tests passed |
| Typecheck / lint | Not run at baseline; run during Phase 13 |

A sandbox temp-directory cleanup warning appeared after pytest completion; it
is an atexit shim artifact and did not affect the test result.

## 4. Live database state (read-only)

| Check | Result |
| --- | --- |
| Migration head | `0022_snapshot_provenance` |
| `geographic_contexts` table | Absent |
| Public tables | 57 |
| Validation datasets | 6, all `nyc311-*` |
| Evidence snapshots | 3 |
| Pilots | 0 |
| RLS on evidence/datasets/pilots/GT/universes | Enabled on all five |
| Schema compatibility for `0023` | All referenced columns (`source_key`, `geographic_coverage`, `dataset_key`, `region`) present |

No writes, migrations, resets or destructive operations were performed.

## 5. Baseline gaps carried into Phase 13

1. No security headers (backend or frontend) and no request correlation IDs.
2. No aggregate readiness endpoint; liveness reported a hardcoded `v1`.
3. No rate limiting on expensive POST endpoints.
4. Production guardrails depend on `APP_ENV=production` (default is `development`).
5. No CI, deployment config, backup/recovery documentation or monitoring runbook.
6. `/validation` and `/pilot` relied on client-side guards only.
7. No dependency lock file and no software-composition analysis.
8. Backend connects with a privileged database role and does not `SET ROLE authenticated`; RLS protects direct PostgREST access only. Application-layer authorization is the effective control boundary.

## 6. Constraints honoured

No NYC dataset was relabelled. No historical evidence, hash or provenance was
rewritten. No model, pilot, alert, dispatch or resource allocation was
activated. No production database write was performed.
