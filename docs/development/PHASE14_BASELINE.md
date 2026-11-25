# CivicFlow — Phase 14 Baseline

Verification date: 2026-11-25 (UTC). This document records what was **directly
verified** at the start of Phase 14 and distinguishes verification strength. It
does not convert local implementation or automated tests into live, real-data,
external or human verification.

Verification categories used throughout Phase 14:

| Category | Meaning |
| --- | --- |
| IMPLEMENTED | Source code / schema / documentation exists in the repository. |
| AUTOMATED-TESTED | Exercised by an automated test in this repository. |
| LIVE-VERIFIED | Directly observed against a running external system during this phase. |
| REAL-DATA-VERIFIED | Verified against non-synthetic operational or authoritative data. |
| HUMAN-VERIFIED | A named human authorized, reviewed or attested to the item. |
| SIMULATED | Synthetic fixture / staging rehearsal only. |
| BLOCKED | A prerequisite is missing or unmet. |
| NOT_ASSESSED | No direct observation was possible in this phase. |

## 1. Git and repository state

| Item | Status | Evidence |
| --- | --- | --- |
| Branch | IMPLEMENTED / LIVE-VERIFIED (local git) | `main` |
| Local HEAD | LIVE-VERIFIED (local git) | `935ec0fad4f8f8335e731913b30a7cae041fff35` |
| Remote | LIVE-VERIFIED (local git) | `origin` → GitHub `Shri7ul/CivicFlow` |
| Remote `main` | LIVE-VERIFIED (`git ls-remote`, 2026-11-25) | `935ec0fad4f8f8335e731913b30a7cae041fff35` — equal to local HEAD |
| Worktree | LIVE-VERIFIED (local git) | clean at phase start |
| Phase 13 commits | IMPLEMENTED | `c842dc3`, `935ec0f` present in history |
| Phase 13 docs/artifacts | IMPLEMENTED | `PHASE13_BASELINE.md`, `PHASE13_REPORT.md`, `PHASE13_SECURITY_AUDIT.md`, `PHASE13_BACKUP_RECOVERY.md`, `PHASE13_MONITORING.md`, `DHAKA_EVIDENCE_READINESS_PHASE13.md`, `verify.yml` |

## 2. Local toolchain

| Item | Status | Evidence |
| --- | --- | --- |
| Backend virtualenv | LIVE-VERIFIED (local filesystem) | `backend/.venv/Scripts/python.exe` present |
| Frontend dependencies | LIVE-VERIFIED (local filesystem) | `frontend/node_modules/.bin/next` present |
| Backend test suite | AUTOMATED-TESTED (Phase 13 record: 269 passed) | re-verified in Phase 14 final verification |
| Frontend test suite | AUTOMATED-TESTED (Phase 13 record: 96 passed) | re-verified in Phase 14 final verification |
| Alembic local head | IMPLEMENTED | `0023_phase12_geography.py`; `down_revision = 0022_snapshot_provenance` |

## 3. Live database (read-only observation)

Connected with a `BEGIN READ ONLY` transaction; no rows were inserted, updated or
deleted and no migration was executed.

| Item | Status | Observation |
| --- | --- | --- |
| Connectivity | LIVE-VERIFIED | connection and read transaction succeeded |
| Alembic head | LIVE-VERIFIED | `0022_snapshot_provenance` (Phase 12/13/14 schema changes **not deployed**) |
| `pilots` table | LIVE-VERIFIED | present, RLS enabled |
| `evidence_snapshots` table | LIVE-VERIFIED | present, RLS enabled |
| `geographic_contexts` table | LIVE-VERIFIED | **absent** (migration 0023 not applied) |
| RLS enforcement | LIVE-VERIFIED (table flag) | `rowsecurity = true` on the two tables inspected |
| Backup existence / restore drill | BLOCKED / NOT_ASSESSED | no verified backup artifact or restore test was available |
| Migration authorization | BLOCKED | no explicit production migration authorization; 0023 and 0024 remain undeployed |

Database credentials exist in a git-ignored local `.env` file (`backend/.env`,
matched by `.gitignore:44`). Their values are deliberately not reproduced here.

## 4. Deployment and external verification

| Item | Status | Observation |
| --- | --- | --- |
| Frontend production URL | NOT_ASSESSED | no deployment URL is recorded in the repository or environment; none was guessed |
| Backend production URL | NOT_ASSESSED | no deployment URL is recorded in the repository or environment; none was guessed |
| HTTPS / security headers (live) | NOT_ASSESSED | no live endpoint available to probe |
| Live `/health/live`, `/health/ready`, `/health/dependencies` | NOT_ASSESSED | implemented and locally AUTOMATED-TESTED only |
| Request ID propagation (live) | NOT_ASSESSED | implemented and locally AUTOMATED-TESTED only |
| Rate limiting (live) | NOT_ASSESSED | production-only; locally AUTOMATED-TESTED only |
| Supabase Auth / Storage connectivity | NOT_ASSESSED | configuration keys present locally; no external call made |
| Remote CI execution | NOT_ASSESSED | `verify.yml` present locally; no CI token or run result available |
| Production log aggregation | NOT_ASSESSED | structured logging implemented; no external log sink verified |

## 5. Application subsystems (local implementation status)

| Subsystem | Status | Notes |
| --- | --- | --- |
| Geographic registry (`US-NYC`, `BD-DHAKA`, `UNKNOWN`) | IMPLEMENTED / AUTOMATED-TESTED | `app/geo/contexts.py`; conservative point/bbox resolution |
| Dhaka readiness engine | IMPLEMENTED / AUTOMATED-TESTED | `app/governance/dhaka_readiness.py`; currently `NOT_READY`, `ready_for_activation=False` |
| General readiness gate | IMPLEMENTED / AUTOMATED-TESTED | `app/governance/readiness.py`; activation server-enforced in pilot transitions |
| Evidence workspace | IMPLEMENTED / AUTOMATED-TESTED | server-side geography scoping and synthetic separation |
| Pilot lifecycle | IMPLEMENTED / AUTOMATED-TESTED | DRAFT→…→COMPLETED/REJECTED/ARCHIVED; no `TERMINATED` state yet |
| Human review (`RiskReviewCase`) | IMPLEMENTED / AUTOMATED-TESTED | append-only decisions, reviewer assignment, separation of duties |
| Ground truth workflow | IMPLEMENTED / AUTOMATED-TESTED | UNVERIFIED→IN_REVIEW→decision; no DRAFT/SUBMITTED/REQUIRES_REVISION state machine |
| Field observation workflow | BLOCKED | no dedicated entity existed before Phase 14 |
| Pilot boundary registration | BLOCKED | no boundary entity existed before Phase 14; screening bbox only |
| Pilot incident handling | BLOCKED | general incidents exist but no pilot-linked severity/state workflow or processing stop |
| Baseline comparison | PARTIAL | metric engine is null-safe; no persisted, pilot-linked comparison workflow |
| Security headers / request IDs | IMPLEMENTED / AUTOMATED-TESTED | Phase 13 |
| Backup/recovery & monitoring docs | IMPLEMENTED | Phase 13 docs; no live drill |

## 6. Verification gaps carried into Phase 14

1. Migration 0023 (and any new Phase 14 migration) undeployed on the live database.
2. No verified backup or restore drill.
3. No production HTTP endpoint available for live verification.
4. No authoritative Dhaka boundary, civic dataset, ground truth, label set or
   validated Dhaka model (all remain BLOCKED / NOT_ASSESSED).
5. No stakeholder approval, legal review, reviewer training record or pilot
   authorization (all HUMAN-VERIFIED prerequisites remain unmet).
6. No verified off-platform CI result.

Phase 14 therefore implements and tests preparation/control infrastructure and
**does not activate** a pilot, a model or operational civic action.
