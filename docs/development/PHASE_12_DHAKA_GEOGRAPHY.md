# Phase 12 — Dhaka Geographic Boundary and Pilot Area Selection

**Status:** GEOGRAPHY REGISTERED; BOUNDARY BLOCKED; PILOT AREA NOT SELECTED
**Date:** 2026-11-25

## 1. Administrative definition — do not interchange boundaries

Dhaka North City Corporation (DNCC), Dhaka South City Corporation (DSCC),
Dhaka District and the Dhaka metropolitan area are **different geographies**.
Before Phase 12 the application used a single Dhaka viewport
(`90.4125, 23.8103`) which is a map centre, not an administrative boundary.

Phase 12 therefore registers **`BD-DHAKA` as a research context with a
rectangular screening envelope**, and records the boundary status as
`BLOCKED`. The envelope is:

| Field | Value |
| --- | --- |
| CRS | EPSG:4326 (WGS84) |
| bbox (GeoJSON: west, south, east, north) | `[90.30, 23.68, 90.50, 23.90]` |
| bbox (lat_min, lon_min, lat_max, lon_max) | `(23.68, 90.30, 23.90, 90.50)` |
| Centre | `23.8103 N, 90.4125 E` |
| Boundary basis | Screening envelope around central Dhaka; **not** a legal or administrative boundary |
| Boundary status | `BLOCKED` |
| Pilot eligible | `false` |
| Operational authority | none recorded |

This envelope is used only to screen coordinates and to detect cross-region
mixing. It must not be published as a DNCC/DSCC boundary.

## 2. Source investigation (actual observations)

All requests below were bounded (`curl`, ≤15 s timeout, research user agent)
from the development environment on 2026-11-25. HTTP status is an observation
of reachability from this environment, **not** proof that a usable dataset or
API exists.

| Source | URL investigated | Observed | Dataset / notes | Status |
| --- | --- | --- | --- | --- |
| Bangladesh Open Data | `https://data.gov.bd/` | HTTP 200 | National portal reachable; no verified machine-readable civic-complaint or ward-boundary API identified in this phase | NOT_ASSESSED |
| DNCC main site | `https://www.dncc.gov.bd/` | connection error (000) | Not reachable from this environment; no dataset acquired | BLOCKED |
| DSCC main site | `https://www.dscc.gov.bd/` | connection error (000) | Not reachable from this environment; no dataset acquired | BLOCKED |
| DNCC GIS portal | `http://eocgis.dncc.gov.bd/` | connection error (000) | Referred to in the UN e-Governance KG 2024 Dhaka submission; no layers acquired | BLOCKED |
| DNCC Emergency Ops geoportal | `http://eocgeoportal.dncc.gov.bd/` | HTTP 200 | Portal landing page reachable; no dataset/API schema verified | NOT_ASSESSED |
| RAJUK | `https://www.rajuk.gov.bd/` | connection error (000) | No planning-boundary layer acquired | BLOCKED |
| Bangladesh Meteorological Department | `https://bmd.gov.bd/` | HTTP 200 | Portal reachable; no verified open weather API contract established | NOT_ASSESSED |
| Bangladesh Bureau of Statistics | `https://www.bbs.gov.bd/` | HTTP 200 | Portal reachable; census/administrative products require separate acquisition and licensing review | NOT_ASSESSED |
| Humanitarian Data Exchange | `https://data.humdata.org/` | HTTP 202 (bot/challenge response) | No dataset downloaded; HDX Bangladesh boundary layers remain a candidate only | NOT_ASSESSED |
| OpenStreetMap Overpass | `https://overpass-api.de/api/interpreter` | HTTP 200, real JSON | Bounded Dhaka research-cell query succeeded; see §4 | REAL-DATA-VERIFIED (research context only) |
| OSM Nominatim status | `https://nominatim.openstreetmap.org/status` | HTTP 200 | Service status only; no bulk geocoding performed | NOT_ASSESSED |

A documented secondary reference (`geobd.com`) lists national geospatial
portals (BNSIS/NSDI, LGED, BWDB) and HDX as candidate sources, and public
reporting describes DNCC Ward 14 works in West Shewrapara / West Kazipara /
Senpara Parbata. None of these were treated as acquired data or as an
authoritative boundary.

## 3. Infrastructure categories

| Category | Authoritative source realistically required | Acquired for pilot? |
| --- | --- | --- |
| DNCC/DSCC/ward boundaries | DNCC/DSCC GIS, RAJUK, BBS/NSDI | No — BLOCKED |
| Roads | LGED / city corporation GIS; OSM as supplementary context | OSM context only |
| Drainage | DNCC/DSCC drainage GIS, Dhaka WASA | No — NOT_ASSESSED |
| Water | Dhaka WASA | No — NOT_ASSESSED |
| Bridges | Public works / city corporation register | No — NOT_ASSESSED |
| Public facilities | City corporation / BBS facility lists | No — NOT_ASSESSED |
| Emergency facilities | DNCC/DSCC emergency ops, health directorate | No — NOT_ASSESSED |
| Transit | RAJUK / transport authority | No — NOT_ASSESSED |
| Flood-prone areas | DDM / BWDB / RAJUK | No — NOT_ASSESSED |
| Waste management | DNCC/DSCC service records | No — NOT_ASSESSED |
| Weather | BMD | No — NOT_ASSESSED |

## 4. Real bounded OSM research cell

A pinned Overpass query was executed against a small central-Dhaka cell:

```
[out:json][timeout:25][maxsize:8000000];
(way[highway](23.78,90.39,23.80,90.41);
 way[bridge](23.78,90.39,23.80,90.41);
 way[waterway](23.78,90.39,23.80,90.41););
out geom;
```

- Cell GeoJSON: `[90.390, 23.780, 90.410, 23.800]`
- Observed OSM base timestamp: `2026-11-24T23:13:20Z`
- Raw response: **447,201 bytes**, SHA-256
  `928c6d919b96f195eb9e6de03f2fbbfe02296878db4c29683161d7a07f281d73`
- Raw elements: **552**; normalized features: **511**; rejected: **41**
- Normalized SHA-256:
  `7b49ff62ab6eaa3a90c87d3a993027ba82033dab1de8b4970f8cbf4de2f50453`
- Artefacts: `backend/data/dhaka/dhaka_osm_context_20261124T231509Z.json.gz` and
  `backend/data/dhaka/MANIFEST.json`
- License: © OpenStreetMap contributors, ODbL 1.0. Attribution is mandatory.
- Data class: `PUBLIC_OSM_RESEARCH_CONTEXT`. **Not** authoritative, **not**
  field-verified, **not** an incident/complaint record, **not** operational
  ground truth.

A separate earlier count probe returned 119 highway ways for
`23.780–23.790, 90.390–90.400`; this was a probe, not an integrated dataset.

## 5. Pilot area shortlist — final selection BLOCKED

| Candidate | Basis | Status | Blockers |
| --- | --- | --- | --- |
| Central Dhaka OSM research cell | Real bounded OSM query; small and geospatially consistent | NOT_ASSESSED | No authoritative boundary; no complaint dataset; no observers/reviewers; no stakeholder agreement |
| Ward 14, DNCC (West Shewrapara / West Kazipara / Senpara Parbata) | Public reporting of DNCC works; named ward | NOT_ASSESSED | Ward polygon not acquired; works reporting is not incident data; no approval |
| Central DSCC wards | Southern city corporation candidate | NOT_ASSESSED | No DSCC/ward boundary; no source assessment; no approval |

**Final selection: BLOCKED.** No geography has been approved. The registry's
`pilot_area_selection_status()` returns `status="BLOCKED"` and
`selected_area=null`. No stakeholder agreement is claimed.

## 6. Geographic data quality controls

Implemented in the geo registry and acquisition path:

- Coordinate bounds validated (`-90..90`, `-180..180`).
- CRS recorded explicitly (EPSG:4326 for all Phase 12 rows).
- Spatial containment: normalized OSM features are checked against the
  registered cell; 41 out-of-cell/invalid elements were rejected and counted.
- Duplicate handling: OSM way ids deduplicated deterministically.
- Missing geometry rejected.
- Unexpected locations: a NYC coordinate in a Dhaka payload is rejected and
  recorded in the quality checks, never silently accepted.
- Freshness: OSM features have **no observation timestamp**; only the retrieval
  time is recorded. No date is invented.
- Provenance: raw/normalized hashes, license, lineage and context key stored.

## 7. Remaining work to unblock geography

1. Acquire authoritative DNCC and DSCC boundary polygons with licence records.
2. Acquire ward polygons and state which corporation each belongs to.
3. Verify at least one official drainage/water/facility source.
4. Obtain stakeholder agreement on a specific pilot area.
5. Update `boundary_status` to `PROVISIONAL` only after evidence, and to
   `AUTHORITATIVE` only after authoritative verification.
6. Only then allow a pilot-approval action; Phase 12 does not approve one.
