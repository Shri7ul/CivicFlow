# Phase 13 Backup and Recovery Readiness

Date: 2026-11-25

This document reports evidence actually found in the repository and verified
against the configured database. It does not claim provider-level backups that
were not observed.

## Status vocabulary

- **Configured** — a setting or artifact exists in the repository.
- **Verified** — confirmed by an observation against a running system.
- **Tested** — an actual restore or recovery drill was executed.
- **Not assessed** — no evidence available to make a determination.
- **Unavailable** — searched for and found absent.

## 1. Findings

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| Database backup configuration in repo | **Unavailable** | No backup script, cron, workflow or IaC found; grep for `backup`, `pg_dump`, `restore`, `pitr`, `replica` returned no configuration artifacts |
| Backup retention policy | **Unavailable** | No policy documented in repository |
| Provider-managed Supabase backups | **Not assessed** | Hosting-level schedules are outside repository evidence; no dashboard/API verification was performed |
| Point-in-time recovery availability | **Not assessed** | Requires provider configuration inspection and credentials; not attempted |
| Restore test | **Not assessed / Not performed** | No separate safe environment was provisioned; no destructive operation performed |
| Database schema migration backup | **Configured (manual)** | `README.md` documents offline Alembic SQL rendering (`alembic upgrade head --sql`) and direct connection upgrades. Offline SQL is a change script, not a full backup |
| Application rollback | **Not assessed** | No deployment config exists; no platform release history was inspected |
| Data-level rollback procedure | **Configured (documented)** | `PHASE_12_DHAKA_PILOT_SOP.md` describes retiring a bad `is_current` snapshot and reinstating the last validated snapshot. This is application-level, not disaster recovery |
| Deployment rollback | **Unavailable** | No deployment platform config or automated rollback found |

## 2. What was verified live (read-only)

- Configured database is reachable and at migration head `0022_snapshot_provenance`.
- 57 public tables, 6 `nyc311-*` validation datasets, 3 evidence snapshots, 0 pilots.
- RLS enabled on evidence snapshots, validation datasets, ground truth records,
  correlation universes and pilots.
- No destructive operation, restore, reset, migration or data write was performed.

## 3. Pre-deployment requirements for migration 0023

The following must be satisfied before `0023_phase12_geography` is applied live:

1. Confirm a recent provider or logical backup exists and record its identifier
   and timestamp (**Not assessed** in this phase).
2. Confirm PITR window covers the deployment time (**Not assessed**).
3. Take a schema-only snapshot of the five tagged tables and the alembic version.
4. Render offline SQL for **review only**:
   `alembic upgrade 0022_snapshot_provenance:0023_phase12_geography --sql`.
   **Do not apply that offline output directly.** Observation: in offline mode
   Alembic does not execute the Python seed loop, so the rendered `INSERT INTO
   geographic_contexts` statements contain `NULL` values for all columns. The
   deployment must use online `alembic upgrade head`, which executes the seed
   loop through a live connection. This is an advisory defect in the committed
   migration and is recorded in `PHASE13_REPORT.md`.
5. Apply during a change window with rollback SQL prepared from the migration's
   `downgrade()` path.
6. Verify post-deployment: head `0023`, `geographic_contexts` has exactly
   `US-NYC` and `BD-DHAKA`, five tagged tables have the new column and index,
   RLS/policy present, and all six NYC dataset keys plus three snapshots retained.

## 4. Honest conclusion

CivicFlow has **no verified backup or tested recovery procedure** in the
repository. Production deployment and any live migration are therefore
**BLOCKED** pending provider backup verification and a documented restore drill
in a separate safe environment. This phase did not create a backup and did not
perform a restore.
