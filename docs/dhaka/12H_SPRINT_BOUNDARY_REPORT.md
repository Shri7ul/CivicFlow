# 12-Hour Sprint — Boundary Report

**Decision:** No boundary is approved for pilot use. This report identifies the strongest candidates and the remaining verification work.

## Evidence hierarchy applied

1. Official government portal / authoritative public boundary service.
2. Authoritative public derivative with explicit source lineage and version.
3. Community-mapped or indirect context.

## Candidate A — BGISP official city corporation and ward services

**Source.** Bangladesh GIS Platform (`gis.gov.bd`) public API and ArcGIS services at `www.arcgisbd.com`.

**Discovery artifacts.**

- `bgisp_api_geocode-layers_.json` — layer catalog; identifies city corporation and union/ward layers.
- `bgisp_api_admin-boundary-layers_.json` — 61-layer catalog with load logs.
- `bgisp_citycorporation_featureserver_242_meta.json`
- `bgisp_unionward_featureserver_245_meta.json`

**Raw geometry.**

- `bgisp_citycorporation_featureserver_242_query.json` — 12 city corporation features; DNCC and DSCC included.
- `bgisp_unionward_featureserver_245_dhaka_query.json` — 254 Dhaka district features; 164 belong to DNCC/DSCC.

**Normalized artifacts.**

| Artifact | Features | SHA-256 |
|---|---:|---|
| `civicflow_dhaka_bgisp_official_city_corporations.geojson` | 2 | `33b586e0f170157bc363ed4d0f306e9bfdf60526200854e16808b1091775701a` |
| `civicflow_dhaka_bgisp_official_dncc_dscc_wards.geojson` | 164 | `15a65b23cc69d6e1ccf6dae2f9c62c4543d7972024c8cab1816ef8bd4632c9be` |

**Attributes verified.**

- CRS: EPSG:4326 / `urn:ogc:def:crs:OGC:1.3:CRS84`.
- DNCC: `city_geo_code=302625`; bbox `[90.328907237, 23.738892653, 90.490360489, 23.900692811]`.
- DSCC: `city_geo_code=302620`; bbox `[90.351719200, 23.669186621, 90.511980260, 23.785339723]`.
- Wards: 76 DNCC + 88 DSCC; 163 unique `union_ward_geo_code` values and 134 unique ward names. Duplicate codes and repeated `(Part)` names require data-quality review.
- All 164 ward representative centroids fall inside their parent city polygon.

**Caveats.** License, copyright text, data vintage, and last edit date are not published in the service metadata. The service is official in origin but unproven in currency and terms of use. It must not be marked `APPROVED` until written confirmation and legal review are recorded.

## Candidate B — HDX COD-AB v03

**Dataset.** Bangladesh Subnational Administrative Boundaries, `cod-ab-bgd`, package ID `401d3fae-4262-48c9-891f-461fd776d49b`.

**Metadata.**

- License: Creative Commons Attribution for Intergovernmental Organisations (CC BY-IGO).
- Version: v03.
- Contributors: OCHA ROAP, OCHA FIS, HDX.
- Metadata modified: `2026-11-23T09:36:36.776738`.
- Valid on: `2023-05-21`; `valid_to` is null.
- Reviewed for accuracy/completeness: `2025-06-01`.
- ADM3 includes `Dhaka North City Corporation` (`BD30262500`) and `Dhaka South City Corporation` (`BD30262000`).

**Artifacts.**

| Artifact | SHA-256 |
|---|---|
| `hdx_cod_ab_bgd_admin_boundaries_geojson.zip` | `ec54c97c2004bbee084afa3f662abb202d8ec038dbfd398af2ebb9b1bf3ec9e5` |
| `civicflow_dhaka_cod_ab_v03_dncc_dscc_candidate.geojson` | `34ce0395f0c6b09a20320d3c66d3b3c12a167522a2660671aec544b8f43bee10` |

**Caveat.** The boundaries are valid from 2023 and may not reflect later ward/city-corporation changes. Attribution is mandatory.

## Candidate C — geoBoundaries ADM4

**Dataset.** `BGD-ADM4-29066614`, 5,160 ADM4 units, boundary year 2020, source BBS/OCHA, license CC BY 3.0 IGO, source data update `2023-01-19`, build date `2026-11-02`.

**Artifacts.**

| Artifact | SHA-256 |
|---|---|
| `geoboundaries_BGD_ADM4_simplified.geojson` | `ce2b675b26abbf347c735f2a834093f736c8238bcc82acad9eeb5e105684124b` |
| `civicflow_dhaka_adm4_ward_candidates_within_cod_ab.geojson` | `b06c1f7648b209afda4835013254f41a11b9efb21e767528c8f87f0c1b50af61` |

**Result.** 138 ADM4 features have centroids inside the COD-AB DNCC/DSCC polygons: 59 in DNCC and 79 in DSCC. Of those, 115 have names beginning with `Ward No-`, but names include duplicate and case-varying `(Part)` records. The underlying boundary year is 2020; this is historical ward context, not proof of current ward boundaries.

The full-resolution ADM4 GeoJSON was downloaded and hashed (`985707373c4ffe631989483617f27af47437b798f50f31a0256e5aaafadb68b6`). It is not versioned because it is 325 MB, and it was removed from the workspace after the hash was recorded; the simplified artifact remains the reproducible versioned boundary evidence.

## Cross-source comparison

| City | COD-AB bbox vs BGISP bbox | Maximum coordinate delta |
|---|---|---:|
| DNCC | `90.328907547..90.490360825` / `23.738893635..23.900693590` vs `90.328907237..90.490360489` / `23.738892653..23.900692811` | `9.82e-7` degrees |
| DSCC | `90.351723098..90.511980704` / `23.669187140..23.785340365` vs `90.351719200..90.511980260` / `23.669186621..23.785339723` | `3.90e-6` degrees |

The two city-corporation layers agree to well under 5 metres in bounding coordinates. This is strong cross-validation, but it is not a legal determination of the current boundary because the BGISP service does not publish a vintage and the COD-AB layer is valid from 2023.

## Rejected candidates

- Nominatim DNCC office polygon — a building/office footprint, not a boundary.
- Existing OSM research cell — a bounded research query, not an administrative boundary.
- RAJUK homepage, NSDI endpoints, GeoDASH and data.gov.bd — no verifiable downloadable boundary found.

## Required next steps before approval

1. Obtain written confirmation from BGISP/RAJUK that feature services 242 and 245 are current authoritative DNCC/DSCC boundaries and wards, including license terms.
2. Record legal review and attribution requirements.
3. Submit a `PilotBoundary` through the existing Phase 14 workflow with distinct verifier and approver.
4. Check duplicate ward codes/names against the authoritative register.
5. Do not auto-approve; no boundary has been promoted in this sprint.
