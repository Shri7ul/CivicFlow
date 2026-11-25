# 12-Hour Sprint — Data Acquisition Report

A provenance manifest with byte sizes, SHA-256 hashes, source URLs, source classes, licenses and operational status is versioned at `backend/data/sprint_boundaries/SPRINT_MANIFEST.json`. All artifacts in that manifest are marked `UNVERIFIED_RESEARCH_EVIDENCE`.

## Acquired boundary and context evidence

| Artifact | Source class | License / terms | Notes |
|---|---|---|---|
| `geoboundaries_ADM2_meta.json`, `geoboundaries_ADM3_meta.json`, `geoboundaries_ADM4_meta.json` | Public derivative | CC BY 3.0 IGO | BBS/OCHA-derived metadata; ADM4 boundary ID `BGD-ADM4-29066614`. |
| `geoboundaries_BGD_ADM2_simplified.geojson`, `geoboundaries_BGD_ADM3_simplified.geojson`, `geoboundaries_BGD_ADM4_simplified.geojson` | Public derivative | CC BY 3.0 IGO | Simplified GeoJSON; ADM4 used for ward-candidate mapping. |
| `hdx_package_401d3fae-4262-48c9-891f-461fd776d49b.json` | Authoritative public | CC BY-IGO | HDX COD-AB v03 package metadata. |
| `hdx_package_8773bbaa-7d4e-4d9a-9e67-4714fd08fd76.json` | Public derivative | ODC-ODbL | HDX geoBoundaries package metadata. |
| `hdx_package_4eb960c7-d7d4-434b-9d53-9988197a6c22.json` | Government/public | CC0 | Bangladesh shape file up to ADM3 metadata; inspected but not used as primary geometry. |
| `hdx_cod_ab_bgd_admin_boundaries_geojson.zip` | Authoritative public | CC BY-IGO | Raw COD-AB v03 geometry archive. |
| `civicflow_dhaka_cod_ab_v03_dncc_dscc_candidate.geojson` | Authoritative public derivative | CC BY-IGO | Normalized DNCC/DSCC candidate boundaries. |
| `bgisp_api_geocode-layers_.json`, `bgisp_api_admin-boundary-layers_.json`, `bgisp_api_get_districts_geocode_filter_.json` | Official government portal | Not stated in public metadata | BGISP discovery and catalog evidence. |
| `bgisp_citycorporation_featureserver_242_meta.json`, `bgisp_citycorporation_featureserver_242_query.json` | Official government service | Not stated in public metadata | Raw official DNCC/DSCC city-corporation geometry. |
| `bgisp_unionward_featureserver_245_meta.json`, `bgisp_unionward_featureserver_245_dhaka_query.json` | Official government service | Not stated in public metadata | Raw official Dhaka union/ward geometry. |
| `civicflow_dhaka_bgisp_official_city_corporations.geojson` | Official service derivative | Not stated in public metadata | Normalized DNCC/DSCC boundaries. |
| `civicflow_dhaka_bgisp_official_dncc_dscc_wards.geojson` | Official service derivative | Not stated in public metadata | Normalized 164 DNCC/DSCC ward candidates. |
| `civicflow_dhaka_adm4_ward_candidates_within_cod_ab.geojson` | Public derivative | CC BY 3.0 IGO | 138 ADM4 candidates inside COD-AB DNCC/DSCC. |
| `SPRINT_VERIFICATION.json`, `sprint_normalized_artifacts.json` | Internal derived | Internal | Cross-source verification and normalized artifact hashes. |

## Acquired contextual evidence

| Artifact | Source | Value | Limitation |
|---|---|---|---|
| `worldbank_BD_SP_URB_TOTL_2015_2025.json` | World Bank API, `SP.URB.TOTL` | 11 annual national urban-population values, 2015–2025; `lastupdated=2026-11-11` | National aggregate; not Dhaka-specific, not a ward label, not ground truth. |

## Deliberately not acquired

- ESA EO4SD flood proxy maps: event-specific historical products from 2019/2020/2023, not current operational evidence.
- BBS census packages: discoverable on HDX, but license/field relevance review was not completed in this sprint.
- FFWC/BMD/DWASA datasets: no direct downloadable GIS/API endpoint was identified; DWASA endpoint also failed TLS validation.
- NSDI/GeoDASH/data.gov.bd: blocked or no usable dataset endpoint.

## Integrity and provenance

- Raw files are preserved under `backend/data/sprint_boundaries/`.
- Normalized artifacts were produced by deterministic extraction from the named raw files; geometry coordinates were not reprojected.
- Every versioned artifact's SHA-256 is checked by `backend/tests/test_sprint_boundary_evidence.py`.
- `SPRINT_MANIFEST.json` records `versioned: false` for artifacts that were inspected and hashed but intentionally not committed, including the 325 MB geoBoundaries full-resolution GeoJSON and the BGISP SPA bundle. Those files were removed from the workspace after their hashes and source URLs were recorded; the versioned artifacts remain sufficient for reproducible verification.

## Operational integration decision

No new source was added to `backend/app/evidence/acquisition.py`. That pipeline ingests bounded **infrastructure asset** snapshots; the acquired sprint data consists of administrative polygons and national indicators. Adding them there would require a new snapshot kind/normalizer and could blur the line between boundary context, infrastructure context and verified incidents. That would be a redesign and is outside the sprint constraint.

Therefore integration was limited to:

1. versioned, hash-pinned research artifacts;
2. a provenance manifest;
3. integrity/safety tests;
4. documentation that explicitly keeps the evidence unverified.

No OSM feature, boundary polygon, World Bank value or model output was promoted into a verified incident, ground-truth label, field observation, pilot approval or production database change.
