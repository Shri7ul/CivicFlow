# CivicFlow API

FastAPI backend for CivicFlow. See the repository root `README.md` for full
setup, environment, testing, and architecture documentation.

Phase 1 through Phase 8 add:

- SQLAlchemy models for 37 application tables and Alembic migrations in
  `alembic/`.
- PostGIS-aware spatial columns and GIST indexes.
- Supabase JWT verification in `app/auth/`.
- Centralized role dependencies and audited profile role management.
- Visibility-scoped incident reporting, editing, department assignment, and a
  forward-only lifecycle with immutable history.
- Private evidence upload with signature/size/filename validation, server-only
  Supabase Storage access, and short-lived signed URLs.
- Viewport bounding-box incident queries and native-map-friendly GeoJSON data.
- Explainable incident correlation, duplicate suggestions, reviewable
  relationships, PostGIS infrastructure proximity, and dependency-aware impact
  foundations.
- A versioned H3 urban risk engine with explainable factors, trends,
  infrastructure exposure, Citizen privacy, GeoJSON cells, and staff snapshots.
- Staff-only decision scenarios, response actions, explicit resource
  assumptions, bounded planning simulation, and strategy comparison. Simulations
  never dispatch, reserve, or mutate operational records.
- Model registry/activation audit, labelled evaluation and calibration metrics,
  provenance-aware idempotent ingestion, freshness monitoring, threshold alerts,
  in-app notifications, and human plan review. Approvals remain non-executing.
- A reproducible NYC 311 public-data snapshot, leakage-safe rolling-origin risk
  backtesting against count/recent/weighted/persistence baselines, sensitivity
  diagnostics, explicitly labelled synthetic correlation/planning evidence,
  append-only validation experiments, and JSON/Markdown reports.
- Deterministic development seed data.

## Commands

```powershell
cd backend

# Migrations (requires a live database; 0002 is Supabase-specific)
$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://..."
.\.venv\Scripts\python.exe -m alembic upgrade head

# Render PostgreSQL DDL without connecting
.\.venv\Scripts\python.exe -m alembic upgrade head --sql

# Development seed (non-production)
.\.venv\Scripts\python.exe -m app.seed

# Reproducible public-data snapshot + experiment records
.\.venv\Scripts\python.exe scripts\ingest_nyc311.py
.\.venv\Scripts\python.exe scripts\generate_validation_report.py --latest

# Tests
.\.venv\Scripts\python.exe -m pytest
```

See [docs/auth-and-rls.md](docs/auth-and-rls.md) for JWT, RBAC, RLS, and
verification-boundary details, [docs/incidents.md](docs/incidents.md) for the
incident API and lifecycle contract, [docs/spatial.md](docs/spatial.md) for
viewport queries, and [docs/evidence.md](docs/evidence.md) for storage/evidence
security and the hosted-policy boundary, and
[docs/intelligence.md](docs/intelligence.md) for Phase 4 scoring, review,
privacy, and data limitations, and [docs/risk-engine.md](docs/risk-engine.md)
for the Phase 5 H3 risk model, API, privacy, and interpretation limits,
[docs/decisions.md](docs/decisions.md) for Phase 6 planning, resources, safety,
and solver limits, and [docs/operations.md](docs/operations.md) for Phase 7
governance, evaluation, ingestion, alerts, approvals, and security, and
[docs/validation.md](docs/validation.md) for Phase 8 dataset selection,
leakage controls, actual metrics, reports, and limitations.

The automated test suite uses isolated SQLite plus offline PostgreSQL SQL
rendering. Live Supabase migration, PostGIS, RLS/ACL, real ES256 sign-in,
provisioning, role changes, incident API flows, private Storage upload/signed download, and headless-browser
map/evidence flows, plus Phase 4 intelligence/relationship, Phase 5 risk,
Phases 6–7 planning/operations, and Phase 8 validation API/browser flows, were
also executed with disposable users and then cleaned up;
see the docs for the exact boundary.
