# Phase 12 — Bangladesh / Dhaka Data Source Discovery and Acquisition

**Status:** ONE REAL RESEARCH SOURCE INTEGRATED; AUTHORITATIVE SOURCES BLOCKED
**Date:** 2026-11-25

## 1. Approach

Phase 11 acquisition controls were reused, not redesigned:

- exact URL allowlist (`SOURCES`), no client-supplied URL (SSRF boundary);
- redirects disabled; timeouts and bounded retries;
- content-type check; streaming byte cap (12 MB for infrastructure);
- record cap (5,000); schema/spatial/CRS validation;
- raw + normalized SHA-256, schema fingerprint, lineage and retained bytes;
- failure-safe snapshots: a failed fetch never retires a valid prior snapshot.

Phase 12 added a geography-aware `SourceDefinition` (context key, normalizer
kind, display name, category, version prefix) with defaults that keep the
historical NYC bridge definition byte-for-byte compatible.

## 2. Source investigation register

Every row records an actual observation. HTTP status is reachability only.

| # | Category | Authority / source | URL | Licence / terms | Coverage | Observed status | Integration |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Civic complaints | Bangladesh Open Data | `https://data.gov.bd/` | Portal terms; per-dataset licence must be checked | National | HTTP 200; no verified complaint API found | NOT_ASSESSED |
| 2 | Administrative boundaries | DNCC GIS / Emergency Ops geoportal | `http://eocgeoportal.dncc.gov.bd/` | Not verified | DNCC | HTTP 200 landing page; no dataset schema verified | BLOCKED |
| 3 | Administrative boundaries | DNCC main / GIS | `https://www.dncc.gov.bd/`, `http://eocgis.dncc.gov.bd/` | Not verified | DNCC | Connection errors from this environment | BLOCKED |
| 4 | Administrative boundaries | DSCC | `https://www.dscc.gov.bd/` | Not verified | DSCC | Connection error | BLOCKED |
| 5 | Planning / boundaries | RAJUK | `https://www.rajuk.gov.bd/` | Not verified | Dhaka region | Connection error | BLOCKED |
| 6 | Statistics / population | BBS | `https://www.bbs.gov.bd/` | Official statistics; licence to be reviewed | National | HTTP 200 portal; no dataset acquired | NOT_ASSESSED |
| 7 | Weather | BMD | `https://bmd.gov.bd/` | Terms to be reviewed | National | HTTP 200 portal; no verified open API contract | NOT_ASSESSED |
| 8 | Boundaries (candidate) | HDX | `https://data.humdata.org/` | Dataset-specific (often ODbL/CC) | National | HTTP 202 challenge response; no dataset downloaded | NOT_ASSESSED |
| 9 | Roads / bridges / waterway context | OpenStreetMap contributors via Overpass API | `https://overpass-api.de/api/interpreter` | ODbL 1.0, mandatory attribution; Overpass usage policy | Bounded central-Dhaka cell | HTTP 200, real JSON | **IMPLEMENTED + REAL-DATA-VERIFIED** |
| 10 | Flooding | DDM / BWDB | No verified public API identified in this phase | — | National | Not acquired | NOT_ASSESSED |
| 11 | Water / drainage | Dhaka WASA | No verified open dataset endpoint identified | — | Dhaka | Not acquired | NOT_ASSESSED |
| 12 | Transit / waste / emergency | City corporation / transport authority | No verified machine-readable source identified | — | Dhaka | Not acquired | NOT_ASSESSED |

No URL or API above was fabricated. Where the source website was reachable but
no dataset contract was verified, the status is `NOT_ASSESSED`, not integrated.

## 3. Implemented integration — Dhaka OSM research context

**Source key:** `dhaka-osm-context-v1`
**Registered context:** `BD-DHAKA`
**Kind:** public community-mapped infrastructure context (research only)

Pinned query and cell are documented in
`PHASE_12_DHAKA_GEOGRAPHY.md` §4. The URL is derived from the query with
`urllib.parse.quote` and stored as a module constant; it is the only Dhaka URL
in the allowlist.

### Verified acquisition (real data)

| Metric | Value |
| --- | --- |
| Raw bytes | 447,201 |
| Raw SHA-256 | `928c6d919b96f195eb9e6de03f2fbbfe02296878db4c29683161d7a07f281d73` |
| Raw Overpass elements | 552 |
| Normalized features | 511 |
| Rejected (invalid/out-of-cell) | 41 |
| Normalized SHA-256 | `7b49ff62ab6eaa3a90c87d3a993027ba82033dab1de8b4970f8cbf4de2f50453` |
| bbox_geojson | `[90.3900972, 23.7800041, 90.4099607, 23.7999428]` |
| OSM base timestamp | `2026-11-24T23:13:20Z` |
| Quality status | WARN (41 rejected features and any out-of-cell geometry vertices, recorded explicitly) |
| Snapshot file | `backend/data/dhaka/dhaka_osm_context_20261124T231509Z.json.gz` |
| Manifest | `backend/data/dhaka/MANIFEST.json` |

### What the integration does

- Normalizes OSM ways to `InfrastructureAsset` rows typed `ROAD`, `BRIDGE` or
  `DRAIN`, with `POINT` geometry in EPSG:4326.
- Stores raw bytes and canonical normalized bytes on the snapshot.
- Records `geographic_context_key=BD-DHAKA`, ODbL attribution, research-cell
  bbox, retrieval time, and an explicit note that the data is not verified
  field infrastructure.
- Sets `data_class=PUBLIC_OSM_RESEARCH_CONTEXT` and `field_verified=false` on
  asset metadata.
- Uses the same allowlist entry point as NYC bridges; an unsupported normalizer
  cannot be reached through it.

### What the integration does not do

- No authoritative claim, no safety claim, no dispatch target.
- No civic complaint, incident or human-verified ground-truth record.
- No per-feature observation timestamp invented (OSM does not supply one).
- No live database write was performed during Phase 12 preparation; the real
  acquisition is preserved as a reproducible on-disk snapshot and manifest,
  and the full DB path is covered by deterministic tests.

## 4. Geographic quality validation

| Check | Result |
| --- | --- |
| Coordinate bounds (-90..90, -180..180) | PASS for 511 records |
| CRS | EPSG:4326 declared by both OSM/Overpass and the snapshot |
| Spatial containment in registered cell | 511 contained; 41 rejected and counted |
| Duplicate OSM ids | 0 after deterministic dedupe |
| Invalid / missing geometry | 41 rejected, recorded in quality checks |
| Unexpected locations (e.g. NYC coordinates) | Rejected by the same containment check |
| Freshness | Only retrieval timestamp; feature freshness NOT_ASSESSED |
| Provenance | Raw hash, normalized hash, licence, lineage, context key present |

## 5. Limitations

- OSM completeness and positional accuracy in Dhaka are unverified.
- OSM is not an authoritative DNCC/DSCC/RAJUK/WASA asset register.
- A warning quality status is honest: the 41 rejected elements are retained in
  the quality ledger rather than hidden.
- No Bangladesh source was integrated as operational evidence.
- Live Supabase/PostgreSQL integration of the Dhaka source was not attempted;
  doing so would create operational-looking rows during a preparation phase.

## 6. Reproduce

```bash
cd backend
./.venv/Scripts/python.exe -c \
  "from app.evidence.acquisition import SOURCES, DHAKA_OSM_SOURCE, fetch_source_bytes; \
   print(len(fetch_source_bytes(SOURCES[DHAKA_OSM_SOURCE].url)))"
```

This performs one bounded request to the pinned allowlisted URL. Respect the
Overpass usage policy; do not loop or scrape.
