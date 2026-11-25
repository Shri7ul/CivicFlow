# Production Migration Review

Date: 2026-11-26
Scope: the complete Alembic chain in `backend/alembic/versions/`, with detailed
review of the two revisions pending on the live database (`0023`, `0024`).
All statements below were inspected in source; no migration was applied.

## 1. Migration sequence

| Item | Verified value |
| --- | --- |
| Migration files | 24, forming one linear chain |
| Local head | `0024_phase14_pilot` (`alembic heads` returns exactly one) |
| Live database head | `0022_snapshot_provenance` (read-only query on configured Supabase) |
| Pending revisions | `0023_phase12_geography`, `0024_phase14_pilot` |
| Chain | `0001_initial_schema` → `0002_auth_rls` → `0003_acl_hardening` → `0004_incident_lifecycle` → `0005_map_evidence_storage` → `0006_incident_intelligence` → `0007_relationship_checks` → `0008_confidence_check_name` → `0009_urban_risk_engine` → `0010_risk_factor_default` → `0011_decision_intelligence` → `0012_operational_maturity` → `0013_phase7_hardening` → `0014_model_version_uniqueness` → `0015_ingested_provenance` → `0016_validation_workspace` → `0017_phase9_diagnostics` → `0018_phase10_pilot_governance` → `0019_phase10_correlation` → `0020_phase11_evidence` → `0021_gt_provenance` → `0022_snapshot_provenance` → `0023_phase12_geography` → `0024_phase14_pilot` |

Do not skip revisions. Do not edit `alembic_version` manually. Verify the live
head before and after the upgrade.

## 2. Preconditions (all currently unmet)

1. **Verified backup and tested restore.** `docs/operations/PHASE13_BACKUP_RECOVERY.md:61-67`
   records no verified backup and no tested recovery. No `pg_dump` binary, no
   backup artifact and no provider-level verification is available in this
   environment. This alone blocks migration.
2. **Confirmed target identity.** The local `.env` is a development profile
   (`APP_ENV=development`, `DEBUG=true`, localhost CORS) pointing at Supabase
   project `wtkrvjnqsdcilvsocayl`. A production migration must confirm the
   intended project ref and a change window before connecting.
3. **Explicit authorization.** No approval record exists for applying `0023`
   or `0024` to the live project.
4. **Read-only baseline snapshot** of `alembic_version`, row counts for the
   five tagged tables, and the RLS policy list.

## 3. Risk review

### 3.1 Migration 0023 — `phase12_geography`

* Creates table `geographic_contexts` plus index `ix_geographic_contexts_country`.
* Seeds **exactly two** rows (`US-NYC`, `BD-DHAKA`) from
  `app.geo.contexts.all_contexts()`.
* Enables RLS, revokes `anon`/`authenticated` privileges, grants `SELECT` to
  `authenticated`, creates `geographic_contexts_read_authenticated`.
* Adds nullable `geographic_context_key` column and index to five tagged
  tables: `evidence_snapshots`, `validation_datasets`, `pilots`,
  `ingested_records`, `ground_truth_records` (see `TAGGED_TABLES`).
* **Backfill data change (not destructive but material):**
  - `evidence_snapshots` rows with `source_key LIKE 'nyc%'` or coverage
    containing "new york" get `US-NYC`.
  - `validation_datasets` rows with `dataset_key LIKE 'nyc311-%'` or region
    containing "new york" get `US-NYC`.
  - `pilots` rows with region containing "dhaka" get `BD-DHAKA`.
  The live database has 3 evidence snapshots, 6 validation datasets and 0
  pilots, so this is a bounded classification update. Verify the affected row
  counts before and after.
* **Known defect:** in `--sql` (offline) mode the Python seed loop does not
  execute, so `INSERT INTO geographic_contexts` contains `NULL` literals.
  **Never apply offline-rendered SQL.** Use online `alembic upgrade`.
* `downgrade()` drops the index/column on tagged tables and drops
  `geographic_contexts`. It reverses schema, but cannot restore the
  original `NULL` context values if new writes occurred after upgrade.

### 3.2 Migration 0024 — `phase14_pilot`

* Creates 11 additive tables: `pilot_boundaries`, `pilot_boundary_events`,
  `field_observations`, `field_observation_events`, `pilot_data_sources`,
  `pilot_incidents`, `pilot_incident_events`, `baseline_comparisons`,
  `pilot_shutdowns`, `phase14_attestations`, `phase14_attestation_events`.
* Adds nullable columns `terminated_at`, `terminated_by`, `termination_reason`
  to `pilots`.
* Replaces CHECK constraints on `pilots` and `pilot_transitions` to add
  `TERMINATED` and related actions; constraint replacement is introspected by
  name and is reversible in `downgrade()`.
* Applies RLS to the new tables (11 `ROW LEVEL SECURITY` statements in offline
  SQL) and contains **no business-data inserts**.
* Offline SQL rendering was verified this sprint: 11 `CREATE TABLE`, 11 RLS
  statements, 0 `INSERT` statements, `TERMINATED` constraints present, and the
  final `alembic_version` update to `0024_phase14_pilot`.
* `downgrade()` restores prior constraints, drops the three added columns,
  removes policies and drops the 11 tables. Irreversible in practice if
  production data is written into the new tables after upgrade.

### 3.3 Whole-chain scan

A keyword scan across all 24 migrations found no `DROP TABLE`, `TRUNCATE`,
`DELETE FROM` or destructive `UPDATE` in any `upgrade()` path. The `DROP
CONSTRAINT` / `DROP COLUMN` hits are confined to constraint replacements and
to migrations `0021`/`0022` that are **already applied** to the live database.
`0003_acl_hardening` hardens (tightens) inherited public-schema ACLs; it is
already applied.

## 4. Recovery strategy

* **Primary:** do not migrate until a provider backup with a known identifier
  and timestamp is confirmed and a restore drill has succeeded in an isolated
  database. Recovery then means restoring that backup, not a hand-written SQL
  patch.
* **Secondary (schema only):** each pending migration has a `downgrade()`
  path. Prepare and review the exact downgrade SQL before the change window.
  Downgrade is only safe if no production writes occurred in the new schema.
* **Application-level:** no data deletion is required on rollback; evidence
  and audit records are additive. `PHASE14_ROLLBACK.md` describes artifact
  rollback and the pilot termination path.
* **Never:** reset the Supabase database, delete production data, or hand-edit
  `alembic_version`.

## 5. Verification queries (run read-only before and after)

```sql
-- Migration identity
select version_num from alembic_version;

-- Expected after upgrade: 0024_phase14_pilot (single row)

-- Contexts: expected US-NYC and BD-DHAKA only
select context_key, country_code, is_pilot_eligible
from public.geographic_contexts order by context_key;

-- Tagged tables carry the new column
select table_name, column_name
from information_schema.columns
where table_schema='public' and column_name='geographic_context_key'
order by table_name;

-- Phase 14 tables present
select tablename from pg_tables
where schemaname='public' and tablename in (
  'pilot_boundaries','field_observations','pilot_incidents',
  'baseline_comparisons','phase14_attestations','pilot_shutdowns')
order by tablename;

-- RLS present on the new tables
select tablename, rowsecurity from pg_tables
where schemaname='public' and rowsecurity
  and tablename like 'pilot_%' order by tablename;

-- Backfill impact (compare to pre-upgrade baseline)
select count(*) filter (where geographic_context_key='US-NYC') from public.evidence_snapshots;
select count(*) filter (where geographic_context_key='US-NYC') from public.validation_datasets;
select count(*) filter (where geographic_context_key='BD-DHAKA') from public.pilots;
```

Expected resulting schema: live head `0024_phase14_pilot`; 2 geographic
contexts; `geographic_context_key` on 5 tagged tables; 11 Phase 14 tables with
RLS enabled; 3 extra nullable columns on `pilots`; existing data counts
(3 snapshots, 6 validation datasets, 0 pilots, 0 ground-truth records)
unchanged except for `geographic_context_key` backfill.

## 6. Verdict

Migration execution: **BLOCKED** — no verified backup/restoration, no confirmed
production target authorization. The SQL itself was reviewed and prepared; no
migration was applied during this sprint.
