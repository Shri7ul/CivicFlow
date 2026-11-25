# 12-Hour Dhaka Evidence Sprint — Final Report

**Sprint scope:** real, verifiable Dhaka evidence acquisition, boundary verification, evidence integration and deployment readiness. No new software phase was created. No pilot was activated, no boundary was approved, no model was activated, and no production change was deployed.

**Repository baseline:** `main` at `65043a7fdfdf3314700e183b6a5976c231eb82a9`, synced with `origin/main` at sprint start. The only pre-existing local change was the untracked sprint data directory created during the sprint.

---

## 1. Sources investigated

All 12 named source categories were investigated:

1. Bangladesh NSDI / SuperMap — HTTP 523; no verifiable public feature service.
2. Bangladesh GIS Portal (`gis.gov.bd`) — HTTP 200; public API and ArcGIS services discovered and queried.
3. RAJUK — HTTP 200; no public GIS download or feature service identified.
4. GeoDASH — DNS resolution failed.
5. Bangladesh Open Data (`data.gov.bd`) — HTTP 200; CKAN endpoints unusable; no geospatial dataset identified.
6. World Bank — API live; national urban-population indicator acquired.
7. ESA EO4SD — site DNS failed; historical flood proxy maps found on HDX but not acquired as current evidence.
8. FFWC — HTTP 200; no downloadable operational GIS feed identified.
9. BMD — HTTP 200; no rainfall/meteorological download identified.
10. DWASA — TLS/connection failure; no drainage dataset identified.
11. BBS — HTTP 200; census packages discoverable on HDX but not acquired or licensed for use in this sprint.
12. Open geospatial sources — geoBoundaries, HDX COD-AB, HDX geoBoundaries and existing OSM research cell acquired/verified.

Full detail: `docs/dhaka/12H_SPRINT_SOURCE_INVENTORY.md`.

## 2. Sources acquired

- **BGISP official services**: city corporation layer 242 and union/ward layer 245, including DNCC/DSCC city polygons and 164 DNCC/DSCC ward candidates.
- **HDX COD-AB v03**: authoritative public ADM0–ADM3 boundaries, including DNCC and DSCC ADM3 features.
- **geoBoundaries ADM2/3/4**: BBS/OCHA-derived metadata and simplified geometry; ADM4 2020 ward candidates used only as cross-check.
- **World Bank API**: `SP.URB.TOTL` for Bangladesh, 2015–2025, `lastupdated=2026-11-11`.
- **Existing OSM research cell**: re-verified as 552 raw elements / 511 normalized research records, not operational evidence.

Raw and normalized artifacts, byte sizes, SHA-256 hashes, source URLs, licenses and statuses are recorded in `backend/data/sprint_boundaries/SPRINT_MANIFEST.json`.

## 3. Sources integrated

No source was added to the operational acquisition pipeline. The acquired sprint data is administrative boundary context and national indicators, whereas `backend/app/evidence/acquisition.py` ingests bounded infrastructure asset snapshots. Adding the new material there would require a new snapshot kind and normalizer and could blur the boundary/context/incident distinction.

Integration was limited to:

- versioned research artifacts under `backend/data/sprint_boundaries/`;
- `SPRINT_MANIFEST.json` provenance manifest;
- `SPRINT_VERIFICATION.json` cross-source verification summary;
- `backend/tests/test_sprint_boundary_evidence.py` with 8 integrity/safety tests;
- this documentation set.

## 4. Boundary status

**Status: strongest evidence identified, but no boundary approved.**

- BGISP official city polygons: DNCC `302625`, DSCC `302620`, EPSG:4326.
- BGISP ward layer: 76 DNCC + 88 DSCC features; 163 unique ward codes and 134 unique names; all 164 centroids inside their parent city polygon.
- COD-AB v03: DNCC `BD30262500`, DSCC `BD30262000`; valid from 2023-05-21; metadata modified 2026-11-23.
- geoBoundaries ADM4: 138 candidates inside COD-AB DNCC/DSCC; 2020 boundary year, 2023 source update; historical context only.
- Cross-source bbox agreement: DNCC max delta `9.82e-7` degrees; DSCC max delta `3.90e-6` degrees.

Blockers to approval: BGISP license and vintage confirmation, legal review, duplicate ward-code review, and formal Phase 14 boundary submission with distinct verifier and approver.

## 5. Data freshness

| Evidence | Freshness statement |
|---|---|
| BGISP services | No vintage or last-edit date in public metadata; currentness unproven. |
| COD-AB v03 | Metadata modified 2026-11-23; boundaries valid from 2023-05-21; reviewed 2025-06-01. |
| geoBoundaries ADM4 | Boundary year 2020; source update 2023-01-19; build date 2026-11-02. Historical/contextual. |
| World Bank | API `lastupdated=2026-11-11`; values are annual national aggregates through 2025. |
| OSM research cell | Retrieved during Phase 12; community-mapped, no guaranteed currency. |

No historical dataset has been represented as current operational evidence.

## 6. Coverage

- Official DNCC/DSCC city polygons acquired and normalized.
- 164 official DNCC/DSCC ward candidates acquired from BGISP.
- 138 geoBoundaries ADM4 candidates inside the COD-AB city polygons.
- 511 normalized OSM research records, all inside DNCC; 0 inside DSCC.
- National World Bank urban population context, not Dhaka-level.

## 7. Ground truth

**None.** No field observation, verified incident, ground-truth assertion, human label or authoritative complaint record was created or discovered during this sprint.

## 8. Model validation

**None.** No model was validated, activated, retrained, promoted or supplied with new labels. The Dhaka model readiness level remains `RESEARCH_ONLY`.

## 9. Pilot area

A defensible shortlist was produced: DNCC, DSCC, and combined DNCC+DSCC. DNCC has the strongest existing research evidence; DSCC has the larger official ward set. No area was selected or approved. See `docs/dhaka/12H_SPRINT_PILOT_AREA_SHORTLIST.md`.

## 10. Production

No production deployment, configuration change, seeding, data migration or service restart was performed. No database connection was used for writes. Live database state was not re-verified in this environment; the last known authoritative observation remains the Phase 14 baseline.

## 11. Migration 0024

Migration `0024_phase14_pilot` was reviewed and re-verified locally:

- Alembic offline PostgreSQL SQL rendered successfully from base to head.
- The 0024 segment creates 11 tables and 11 RLS statements.
- The 0024 segment contains 0 business-data `INSERT` statements.
- `TERMINATED` pilot status/action constraints are present.
- Alembic version update to `0024_phase14_pilot` is present.
- SQLite upgrade/downgrade test passed in the full backend suite.
- No migration was applied to any live or production database.

## 12. Security

- No secrets, private keys, service-role keys, database credentials or tokens were found in the sprint diff.
- No client-supplied URL acquisition path was added.
- No SSRF-relevant endpoint was added.
- Auth, RBAC, RLS and existing readiness gates were not modified.
- No private, personal or unauthorized dataset was acquired.
- Source URLs are public official/API endpoints or public research datasets with recorded license/terms.

## 13. Tests

- New sprint suite: **8 passed** (`backend/tests/test_sprint_boundary_evidence.py`).
- Full backend suite: **304 passed**.
- Frontend suite: **96 passed**, 30 files.
- Geographic isolation, provenance, integrity, migration and final-gate tests from prior phases remained green.
- No test was weakened to accommodate sprint artifacts.

## 14. Blockers

1. Written BGISP/RAJUK confirmation of authority, currency and license for services 242 and 245.
2. Legal review and attribution requirements for CC BY-IGO, CC BY 3.0 IGO, ODC-ODbL and unstated BGISP terms.
3. Duplicate ward-code/name resolution against an authoritative register.
4. Field validation and explicit ground-truth promotion through Phase 14 workflows.
5. Independent model validation; model remains `RESEARCH_ONLY`.
6. Verified backup/restore evidence and authorized migration deployment.
7. Human selection of a bounded pilot area and explicit pilot activation authorization.

## 15. Git

Sprint work is staged and committed only after the checks above. No force-push, no secret-bearing file, no private data and no unauthorized dataset are included. Commit hash and push status are recorded in the final git output for this sprint.

## Final verdict

| Category | Verdict |
|---|---|
| Sources investigated | All 12 categories investigated; 4 yielded usable evidence, 8 blocked or no dataset identified. |
| Sources acquired | BGISP official boundaries/wards, HDX COD-AB v03, geoBoundaries ADM2/3/4, World Bank national indicator. |
| Sources integrated | Research artifacts, manifest, verification summary, tests and docs only; no operational pipeline change. |
| Boundary | Strong candidates identified; none approved. |
| Freshness | COD-AB current metadata but 2023 validity; BGISP vintage unknown; geoBoundaries historical. |
| Coverage | DNCC/DSCC city polygons, 164 official ward candidates, 138 ADM4 candidates. |
| Ground truth | None. |
| Model validation | None; model remains research-only. |
| Pilot area | Shortlist only; no selection. |
| Production | Unchanged; no deployment. |
| Migration 0024 | Reviewed, offline SQL valid, not deployed. |
| Security | No secrets or private data found; no new auth/SSRF surface. |
| Tests | 8 sprint + 304 backend + 96 frontend passed. |
| Readiness | Not ready for pilot; all prior Phase 14 blockers remain. |
