# Phase 12 — Dhaka Localization Audit

**Status:** IMPLEMENTED (architecture), BLOCKED (pilot approval)
**Date:** 2026-11-25
**Method:** Read-only repository inspection of the Phase 11 tree at `a3babc9`, followed by additive implementation.

## 1. Purpose

Audit every place where New York City assumptions exist and introduce a geographic
context architecture that permits NYC research, Dhaka research, and future
Bangladesh cities to coexist **without relabelling or rewriting history**.

No historical NYC dataset, snapshot, hash, experiment, or provenance value was
modified.

## 2. Central finding

The repository had a **dual geography**:

| Layer | Geography before Phase 12 | Evidence |
| --- | --- | --- |
| Operational UI / seed assets | Already Dhaka | `frontend/src/lib/map.ts:6-10` (viewport 90.4125, 23.8103); `backend/app/seed.py` (Dhaka WKT assets); `frontend/src/app/incidents/new/report-incident-form.tsx:34-35` |
| Research / validation / evidence | Entirely NYC | `backend/app/validation/dataset.py:22-142` (4 pinned NYC 311 specs); `backend/app/validation/phase11.py:14-46` (2 fresh NYC Q3 slices); `backend/app/evidence/acquisition.py:37-85` (NYC DOT bridges) |

There was **no** `Region`, `Geography`, `GeographicContext`, `Scope`,
`Jurisdiction`, `DatasetRegistry` or `SourceRegistry` model or enum. Region was
free text on `ValidationDataset`, `ValidationExperiment` and `Pilot`; bbox was
raw JSON with **three incompatible orderings**:

1. `(lat_min, lon_min, lat_max, lon_max)` in dataset specs
2. GeoJSON `(west, south, east, north)` in `EvidenceSnapshot.bbox`
3. API bbox `(min_lat, min_lon, max_lat, max_lon)` in risk/query code

## 3. NYC assumptions found and disposition

| Location | Assumption | Disposition |
| --- | --- | --- |
| `validation/dataset.py:22-142` | 4 pinned NYC 311 specs, NYC bboxes, NYC complaint-type maps | **Preserved unchanged.** Remains the historical research registry. |
| `validation/phase11.py:14-46` | 2 fresh NYC Q3 2026 slices | **Preserved unchanged.** Historical results stay reproducible. |
| `evidence/acquisition.py:37-85` | NYC bridge URL, `NYC_BBOX`, single-source registry | **Preserved + generalized.** `SourceDefinition` now carries geography, normalizer kind, display name, category and version prefix with NYC-compatible defaults. |
| `evidence/acquisition.py:132-139` | `_valid_coordinates()` bounded to `NYC_BBOX` | **Left intact for bridges**; the new Dhaka source uses its own pinned cell normalizer. |
| `evidence/workspace.py:91` | `dataset_key.like("nyc311-%-2026q3")` fresh-holdout detection | **Gated.** NYC holdouts and bridge overlap are exposed only when the workspace is unscoped or `US-NYC`. |
| `validation/research.py:108` | `if "brooklyn" in dataset.dataset_key` | **Preserved** — historical analysis code; never applied to Dhaka keys. |
| `validation/*.py` synthetic fixtures | `40.69..., -73.98...` H3 cells | **Preserved** — explicitly synthetic test fixtures only. |
| `frontend/src/lib/map.ts:6-10` | Hardcoded Dhaka viewport constant | **Centralized.** Now derived from `src/config/geography.ts`. |
| `frontend/src/components/pilot/*` | No region selector | **Extended** with an API-backed geographic panel on `/pilot`. |

## 4. Implemented localization architecture

### 4.1 Central registry (single source of truth)

`backend/app/geo/contexts.py` defines:

- `GeographicContext` with `key`, country, kind, **bbox**, centre, CRS,
  provenance basis, boundary basis, **boundary status**, pilot eligibility,
  source URLs and notes.
- `US-NYC` — historical research geography; `is_pilot_eligible=False`.
- `BD-DHAKA` — research/pilot-candidate identity; `boundary_status=BLOCKED`,
  `is_pilot_eligible=False`.
- `BoundingBox` with explicit `from_latlon()` / `from_geojson()` conversion so
  the three historical bbox conventions can no longer be mixed by hand.
- Conservative resolution: `resolve_context_from_point()` and
  `resolve_context_from_bbox()` return `UNKNOWN` for ambiguous or out-of-range
  input. No coordinate is silently relabelled.
- `pilot_area_selection_status()` — final selection is `BLOCKED`.

Frontend mirror: `frontend/src/config/geography.ts` (configuration only; the API
remains authoritative at runtime).

### 4.2 Database-backed context

Migration `0023_phase12_geography` (head, after `0022_snapshot_provenance`):

- Creates `geographic_contexts` with RLS enabled, privileges revoked from
  `anon`/`authenticated`, SELECT granted to `authenticated`, and a read policy.
- Seeds one row per registered context from the registry.
- Adds `geographic_context_key` (default `UNKNOWN`, indexed) to
  `evidence_snapshots`, `validation_datasets`, `ground_truth_records`,
  `correlation_universes`, `pilots`.
- **Backfill is conservative and non-rewriting:** only rows whose existing
  `dataset_key`/`source_key`/`region`/`geographic_coverage` already prove NYC or
  Dhaka geography are labelled; everything else stays `UNKNOWN`. No hash,
  record count, provenance kind, snapshot file or experiment is changed.

### 4.3 Server-side isolation

- `build_workspace(..., geographic_context_key=...)` filters datasets,
  snapshots, ground truth, universes and infrastructure sources server-side;
  NYC holdout results and bridge overlap are excluded from a Dhaka workspace.
- `GET /governance/evidence/workspace?geographic_context=BD-DHAKA` validates the
  key against the registry and rejects unknown keys with HTTP 422.
- New `GET /governance/geography/*` endpoints expose contexts, pilot shortlist,
  Dhaka readiness, context-scoped datasets/snapshots and an isolation report.
- `serialize_snapshot()` now emits `geographic_context_key`.

### 4.4 Dhaka-specific readiness

`backend/app/governance/dhaka_readiness.py` is additive to the Phase 11
readiness engine. It computes 20 categories from **persisted BD-DHAKA evidence**
only. Missing evidence yields `BLOCKED`/`NOT_ASSESSED`, never `PASS`. It always
returns `ready_for_activation=False` and `pilot_activation_authorized=False`.

## 5. Geographic identity decisions

- `BD-DHAKA` is a **registered identity**, not a magic string; all new code uses
  the registry or its database mirror.
- The Dhaka bbox is a **research screening envelope**, not DNCC, DSCC, district
  or metropolitan boundary. Boundary status is `BLOCKED`.
- OSM is treated as **community-mapped context**, not authoritative
  infrastructure.
- Historical NYC data stays `US-NYC`; its results are never Dhaka performance.

## 6. Verification

- Offline migration upgrade/downgrade test passes at new head
  `0023_phase12_geography`; model/migration column sets match.
- 19 new deterministic tests cover registry, bbox conversion, cross-context
  classification, pilot status, acquisition, workspace isolation, readiness and
  API authorization. Synthetic fixtures are never counted as operational
  evidence.
- Full backend suite and full frontend suite pass. See
  `PHASE_12_IMPLEMENTATION_REPORT.md`.

## 7. Remaining work

1. Acquire authoritative DNCC/DSCC/ward boundaries and set boundary status.
2. Obtain at least one non-OSM authoritative Dhaka source.
3. Establish Dhaka ground truth, correlation universes and external validation.
4. Stakeholder engagement and approval before any pilot activation.
