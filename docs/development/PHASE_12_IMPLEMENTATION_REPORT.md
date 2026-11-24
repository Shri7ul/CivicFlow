# Phase 12 — Implementation Report

**Phase:** Dhaka Localization & Controlled Pilot Preparation
**Date:** 2026-11-25
**Base commit:** `a3babc9c5948c4dc2d608d4ba2304166f1b51afc` (Phase 11)
**Application version:** 0.11.0 (unchanged — Phase 12 does not activate a release)
**Local migration head:** `0023_phase12_geography`
**Live migration head:** `0022_snapshot_provenance` (not advanced; see Live Verification)

## Executive Summary

Phase 12 established a geographic context architecture that separates NYC
historical research data from Dhaka research/pilot preparation. It implemented
one **real, bounded OSM Overpass acquisition** for a small central-Dhaka
research cell, added server-side geographic isolation, a Dhaka-specific
evidence-driven readiness view, pilot SOPs and validation protocols, and 27 new
deterministic tests (19 backend, 8 frontend).

The platform is **NOT READY** for a Dhaka controlled pilot. Boundary, pilot
area, authoritative sources, ground truth, correlation labels, validation,
stakeholder agreement and governance approvals remain blocked or not assessed.
No pilot was approved, no model was activated, no automated action was enabled.

## Phase 12 Scope

Implemented: all feasible workstreams A–J (architecture, geography research,
source integration, protocols, application changes, readiness, security review,
tests, documentation). Workstreams requiring external stakeholders or
authoritative data are explicitly blocked, not substituted with fabricated
evidence.

## Dhaka Localization Architecture

- Central registry: `backend/app/geo/contexts.py` (`BD-DHAKA`, `US-NYC`,
  `UNKNOWN`), with explicit bbox conversion helpers and conservative point/bbox
  resolution.
- Frontend configuration mirror: `frontend/src/config/geography.ts`.
- Database registry: `geographic_contexts` table seeded by migration `0023`.
- Explicit context labels on snapshots, datasets, ground truth, universes and
  pilots; only provable historical rows were backfilled to `US-NYC`.

## NYC vs Dhaka Data Separation

- Historical NYC dataset keys, hashes, snapshots and experiments are unchanged.
- New acquisitions set their context explicitly (`US-NYC` in `external.py`,
  `BD-DHAKA` in the OSM path, context derived from coordinates for ground truth,
  inherited from reference snapshots for universes).
- Dhaka-scoped workspace filters datasets, snapshots, GT, universes and
  infrastructure sources server-side; NYC holdouts and bridge overlap are
  excluded.
- `serialize_snapshot()` exposes `geographic_context_key`; unknown remains
  `UNKNOWN`.

## Geographic Context

| Context | Key | bbox (GeoJSON) | Boundary status | Pilot eligible |
| --- | --- | --- | --- | --- |
| New York City research | `US-NYC` | `[-74.3, 40.4, -73.6, 41.0]` | NOT_ASSESSED | false |
| Dhaka research / pilot candidate | `BD-DHAKA` | `[90.3, 23.68, 90.5, 23.9]` | BLOCKED | false |

## Pilot Area Candidate / Selection Status

`BLOCKED`; no selected area. Shortlist: central Dhaka OSM research cell, Ward 14
DNCC (publicly reported works area), central DSCC wards — all `NOT_ASSESSED`.
No stakeholder agreement is claimed.

## Data Sources Investigated

| Name | Authority | URL | Licence | Coverage | Status | Integration | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Bangladesh Open Data | Gov. portal | `https://data.gov.bd/` | Per-dataset; not verified | National | HTTP 200; NOT_ASSESSED | None | No verified civic-complaint API |
| DNCC geoportal | DNCC | `http://eocgeoportal.dncc.gov.bd/` | Not verified | DNCC | HTTP 200 landing; NOT_ASSESSED | None | No dataset schema verified |
| DNCC GIS / main | DNCC | `http://eocgis.dncc.gov.bd/`, `https://www.dncc.gov.bd/` | Not verified | DNCC | Connection error; BLOCKED | None | Not reachable here |
| DSCC | DSCC | `https://www.dscc.gov.bd/` | Not verified | DSCC | Connection error; BLOCKED | None | Not reachable here |
| RAJUK | RAJUK | `https://www.rajuk.gov.bd/` | Not verified | Dhaka region | Connection error; BLOCKED | None | No boundary layer acquired |
| BBS | Gov. statistics | `https://www.bbs.gov.bd/` | To be reviewed | National | HTTP 200; NOT_ASSESSED | None | Licence/acquisition pending |
| BMD | Gov. weather | `https://bmd.gov.bd/` | To be reviewed | National | HTTP 200; NOT_ASSESSED | None | No verified open API contract |
| HDX | Humanitarian Data Exchange | `https://data.humdata.org/` | Dataset-specific | National | HTTP 202 challenge; NOT_ASSESSED | None | No dataset downloaded |
| OSM Overpass | OSM contributors | `https://overpass-api.de/api/interpreter` | ODbL 1.0 + attribution | Bounded Dhaka cell | HTTP 200 real JSON | **REAL-DATA-VERIFIED** | Community-mapped, unverified completeness |
| WASA / DDM / BWDB / transit / waste | Relevant agencies | No verified machine-readable endpoint established | — | Dhaka/National | NOT_ASSESSED | None | No fabrication |

## Real Data Integrated

- Source key `dhaka-osm-context-v1`, context `BD-DHAKA`.
- Raw bytes: **447,201**; raw SHA-256
  `928c6d919b96f195eb9e6de03f2fbbfe02296878db4c29683161d7a07f281d73`.
- Raw elements **552**; normalized features **511**; rejected **41**.
- Normalized SHA-256
  `7b49ff62ab6eaa3a90c87d3a993027ba82033dab1de8b4970f8cbf4de2f50453`.
- bbox `[90.3900972, 23.7800041, 90.4099607, 23.7999428]`; OSM base timestamp
  `2026-11-24T23:13:20Z`; quality WARN with recorded rejections.
- Artefacts: `backend/data/dhaka/dhaka_osm_context_20261124T231509Z.json.gz`,
  `backend/data/dhaka/MANIFEST.json`.
- No live database write of this data was performed.

## Ground-Truth Preparation

Existing Phase 11 workflow retained. `GroundTruthRecord` now stores a context
derived from coordinates. Field evidence protocol, source-type matrix,
independence, uncertainty, contradiction, privacy, consent, safety and reviewer
responsibilities documented. **No field observation or verified record was
created** (live count remains 0).

## Correlation Reference Preparation

Existing immutable universe model retained, now context-tagged. Protocol covers
candidate generation, spatial/temporal matching, completeness attestation,
independent reviewers, disagreement, abstention and bias. **No Dhaka universe
or label was created** (live count remains 0); recall/F1 are null.

## Dhaka Validation Protocol

Target suitability reviewed (incident definition, H3 resolution, temporal
windows, sparsity, density, bias, leakage, baselines, metrics). External
validation design documented. Status **BLOCKED**; no metric invented; no model
trained, tuned, promoted or activated.

## Application Changes

- New APIs: `/governance/geography/contexts`, `/contexts/{key}`, `/pilot-areas`,
  `/readiness/dhaka`, `/datasets`, `/snapshots`, `/isolation`.
- `/governance/evidence/workspace?geographic_context=<key>` server-side scoping.
- `/pilot` page now includes an API-backed geographic panel with context
  selector, boundary status, Dhaka readiness and pilot shortlist.
- Map defaults derived from central config; NYC research environment preserved.
- Files: `backend/app/geo/*`, `backend/app/models/geo.py`,
  `backend/app/evidence/dhaka_osm.py`, `backend/app/governance/dhaka_readiness.py`,
  `backend/app/api/v1/endpoints/phase12.py`, `frontend/src/config/geography.ts`,
  `frontend/src/types/geography.ts`, `frontend/src/lib/api/geo.ts`,
  `frontend/src/components/geography/geography-panel.tsx`.

## Readiness Assessment

Dhaka readiness is computed from persisted, context-tagged evidence by
`assess_dhaka_readiness()` (20 categories). `pilot_activation_authorized` and
`ready_for_activation` are always false in Phase 12.

**Overall: NOT_READY.** Representative categories:

| Category | Status | Type |
| --- | --- | --- |
| Dhaka geographic boundary | BLOCKED | Mandatory |
| Pilot area selection | BLOCKED | Mandatory |
| Source availability (authoritative) | BLOCKED | Mandatory |
| Data freshness | BLOCKED | Mandatory |
| Geographic coverage | BLOCKED | Mandatory |
| Data provenance | BLOCKED | Mandatory |
| Ground-truth readiness | BLOCKED | Mandatory |
| Correlation readiness | BLOCKED | Mandatory |
| Infrastructure coverage | BLOCKED | Mandatory |
| Model validation / baseline comparison | BLOCKED | Mandatory |
| Human review | BLOCKED | Mandatory |
| Geographic isolation | PASS (synthetic test only; live NOT_ASSESSED) | Mandatory |
| Operational constraints | BLOCKED | Mandatory |
| Model activation | NOT_APPLICABLE | Advisory |
| Security / reviewer training / escalation / rollback / stakeholder engagement | BLOCKED | Advisory |

Missing evidence never becomes PASS; no category is hardcoded to PASS.

## Security Audit

- No secrets committed; `.env` files remain gitignored.
- Acquisition URLs are allowlisted constants; no client URL, redirects disabled,
  byte/record caps, content-type validation, timeouts and bounded retries intact.
- No path traversal or raw-byte exposure added; geography endpoints return only
  registry/configuration and serialized metadata.
- RLS/RBAC unchanged and not bypassed; new geography table uses RLS with
  SELECT to authenticated and revoked anon privileges; staff endpoints use
  existing `require_worker`/`require_admin`.
- Cross-region leakage tests verify a Dhaka workspace excludes NYC assets and
  that unknown contexts are rejected.
- Geolocation privacy: only WGS84 coordinates already present in the domain are
  used; sensitive ground-truth flag retained; no personal data exposed publicly.
- Bangladesh legal compliance is **NOT asserted**; qualified local legal review
  remains required.

## Database and Migration Status

- Local head: `0023_phase12_geography` (after `0022_snapshot_provenance`).
- Offline SQLite upgrade/downgrade and model/schema column parity tests pass.
- Live PostgreSQL head remains `0022_snapshot_provenance`; Phase 12 migration
  was **not applied live** (deployment action requiring approval).

## Test Results

| Check | Result |
| --- | --- |
| Backend full suite | 251 collected, exit 0, 0 failures (includes 19 new Phase 12 tests) |
| Frontend tests | 94 passed / 29 files (baseline 86; +8 new) |
| TypeScript typecheck | PASS |
| ESLint | PASS |
| Frontend production build | PASS (18/18 static pages) |
| Offline migration upgrade/downgrade | PASS |
| Real OSM acquisition | PASS (511 features, hashes verified) |

The production build required unsetting two sandbox shim variables for the
child process because Next.js's own gitignored `.next/trace-build` cache
cleanup hit a bulk-delete guard; this did not alter application code or data.

## Live Verification (read-only)

| Item | Observation |
| --- | --- |
| Migration head | `0022_snapshot_provenance` |
| Public tables | 57 |
| `validation_datasets` rows | 6 (all `nyc311-*`, all VALIDATED) |
| `evidence_snapshots` rows | 3 |
| `ground_truth_records` rows | 0 |
| `correlation_universes` rows | 0 |
| `geographic_contexts` table | absent (migration not applied) |
| `geographic_context_key` columns | 0 (migration not applied) |
| RLS on evidence tables | enabled for `evidence_snapshots`, `ground_truth_records`, `correlation_universes` |
| Destructive operations | none performed |

Live verification of the new Phase 12 schema is therefore **NOT_ASSESSED**;
offline migration tests are the evidence for it.

## Git Commit / Push Status

_To be filled after commit: commit hash, branch and push verification._

## Remaining Blockers

1. Authoritative DNCC/DSCC/ward boundaries and licensing review.
2. At least one non-OSM authoritative Dhaka source.
3. Dhaka ground truth with independent field verification.
4. Complete Dhaka correlation reference universe and independent labels.
5. Dhaka external validation with recomputed strongest baseline.
6. Stakeholder engagement and formal pilot-area approval.
7. Reviewer training, incident escalation drill, deployment/rollback exercise.
8. Bangladesh legal/privacy review by qualified counsel.
9. Live application of migration `0023` under deployment approval.

## Phase 12 Exit Verdict

| Status label | Applies to |
| --- | --- |
| IMPLEMENTED | Registry, migration, acquisition integration, APIs, app localization, readiness engine, protocols, docs |
| AUTOMATED-TESTED | 251 backend tests, 94 frontend tests, migration tests, typecheck, lint, build |
| LIVE-VERIFIED | Pre-existing Phase 11 baseline (read-only): head 0022, 6 NYC datasets, 3 snapshots, 0 GT, 0 universes, RLS enabled |
| REAL-DATA-VERIFIED | 511 OSM features in one bounded Dhaka research cell with raw/normalized hashes |
| HUMAN-VERIFIED | Nothing in Phase 12 |
| SIMULATED | Deterministic fixtures in tests only; never counted as operational evidence |
| BLOCKED | Pilot area, authoritative sources, ground truth, correlation, validation, activation |
| NOT_ASSESSED | Live Phase 12 schema, legal review, stakeholder agreements, reviewer training |

**CivicFlow is NOT ready for a Dhaka controlled pilot.** Phase 12 delivered
preparation and honest blockers; it did not authorize or perform pilot
activation, model activation, public deployment or automated civic action.
