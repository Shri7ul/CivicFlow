# Dhaka Evidence Readiness — Phase 13

Date: 2026-11-25
Scope: can the current application **safely ingest** future legitimate Dhaka
evidence? This is a capability audit, not a claim that data exists or that
sources are integrated.

Status legend: **REAL-DATA-VERIFIED**, **AVAILABLE-NOT-INTEGRATED**,
**NOT_ASSESSED**, **BLOCKED**, **INTEGRATED-RESEARCH-ONLY**.

## 1. Pipeline capability assessment

| Capability | Status | Evidence |
| --- | --- | --- |
| Exact source allowlist | **IMPLEMENTED** | `app/evidence/acquisition.py`, `SOURCES` registry |
| No arbitrary client URLs / redirects disabled | **IMPLEMENTED / TESTED** | Phase 12 tests reject non-allowlisted URLs |
| Bounded requests, timeouts, byte/record caps | **IMPLEMENTED** | Phase 11/12 acquisition controls |
| Content-type, schema, spatial and CRS validation | **IMPLEMENTED** | Acquisition + `app/evidence/dhaka_osm.py` normalizer |
| Geographic tagging of new records | **IMPLEMENTED / TESTED** | `geographic_context_key` on snapshots/datasets/GT/universes/pilots |
| Raw + normalized SHA-256 provenance | **IMPLEMENTED / REAL-DATA-VERIFIED** | Verified Dhaka OSM snapshot manifest |
| Research vs operational separation | **IMPLEMENTED / TESTED** | OSM serializes as `PUBLIC_OSM_RESEARCH` / `RESEARCH_CONTEXT_ONLY` |
| Human ground-truth workflow | **IMPLEMENTED (framework only)** | Phase 11 workflow, geography-tagged; **no Dhaka field record exists** |
| Correlation universe workflow | **IMPLEMENTED (framework only)** | No Dhaka universe or labels exist |
| Authoritative boundary ingestion | **BLOCKED** | No verified DNCC/DSCC/RAJUK boundary dataset |
| Complaint/civic-service source | **BLOCKED** | No verified machine-readable official API |
| Field observation intake | **NOT_ASSESSED** | Protocol documented in Phase 12; no collection deployed |

## 2. Source register (evidence-based only)

| Source | Owner | Scope | Access / format | Availability | Integration | Licence | Freshness | Quality | Operational relevance | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenStreetMap Overpass (`overpass-api.de`) | OpenStreetMap community | Bounded central-Dhaka research cell `[90.3900972, 23.7800041, 90.4099607, 23.7999428]` | HTTPS JSON query, allowlisted exact URL | **REAL-DATA-VERIFIED** (HTTP 200, real JSON) | **INTEGRATED-RESEARCH-ONLY** | ODbL, attribution required | OSM base `2026-11-24T23:13:20Z` | 552 raw → 511 normalized, 41 rejected; community-mapped | Context only; **not authoritative**, not operational evidence | No official assurance, no complete feature inventory, no civic complaint semantics |
| Bangladesh Open Data (`data.gov.bd`) | Government of Bangladesh | National | Web portal | HTTP 200; **AVAILABLE-NOT-INTEGRATED** | None | Not verified | Not assessed | Not assessed | Potential catalogue only | No verified complaint API or machine-readable schema found |
| DNCC geoportal (`eocgeoportal.dncc.gov.bd`) | Dhaka North City Corporation | DNCC | Web landing page | HTTP 200; **AVAILABLE-NOT-INTEGRATED** | None | Not verified | Not assessed | Not assessed | Potential authoritative boundary/infrastructure | Landing page only; no dataset schema, download or API verified |
| DNCC main / GIS (`dncc.gov.bd`, `eocgis.dncc.gov.bd`) | DNCC | DNCC | Web / GIS | Connection error from this environment; **BLOCKED** | None | Not verified | Not assessed | Not assessed | Authoritative if accessible | Unreachable here; no integration claimed |
| DSCC (`dscc.gov.bd`) | Dhaka South City Corporation | DSCC | Web | Connection error; **BLOCKED** | None | Not verified | Not assessed | Not assessed | Authoritative if accessible | Unreachable here |
| RAJUK (`rajuk.gov.bd`) | RAJUK | Dhaka metropolitan planning | Web | Connection error; **BLOCKED** | None | Not verified | Not assessed | Not assessed | Potential planning/boundary authority | No boundary layer verified |
| BBS (`bbs.gov.bd`) | Bangladesh Bureau of Statistics | National | Web | HTTP 200; **AVAILABLE-NOT-INTEGRATED** | None | Not verified | Not assessed | Not assessed | Population/ward context if licensed | Licence and acquisition path unverified |
| BMD (`bmd.gov.bd`) | Bangladesh Meteorological Department | National | Web | HTTP 200; **AVAILABLE-NOT-INTEGRATED** | None | Not verified | Not assessed | Not assessed | Weather/flood context | No verified API |
| HDX (`data.humdata.org`) | OCHA / HDX | Bangladesh | Web/API | HTTP 202 challenge; **NOT_ASSESSED** | None | Dataset-specific | Not assessed | Not assessed | Possible authoritative adjunct | Bot challenge prevented download; no dataset asserted |
| BWDB / WASA / DDM / transit / waste | Various agencies | Bangladesh / Dhaka | No verified machine-readable endpoint | **NOT_ASSESSED** | None | Not verified | Not assessed | Not assessed | High if available | No source, API or licence verified; nothing fabricated |

## 3. Ingestion requirements for any future source

Before a source is added to `SOURCES`, it must have:

1. A verified owner and official URL; licence/attribution recorded.
2. A pinned URL or exact allowlist entry; no client-supplied URLs.
3. Documented CRS, bbox and update frequency; spatial containment checks.
4. Deterministic normalization with raw and normalized SHA-256.
5. `geographic_context_key = BD-DHAKA` assigned explicitly, never inferred silently.
6. A classification as `PUBLIC_*`, `RESEARCH_*`, or `OPERATIONAL` with a
   verification status. No source is operational by default.
7. A freshness check and a bounded record count.
8. Reviewer/legal approval for any personal or location-level data.

## 4. Honest conclusion

CivicFlow's acquisition and provenance machinery is **capable** of ingesting
future authoritative Dhaka data without conflating it with NYC research or OSM
context. However, **no authoritative Dhaka source is currently integrated**,
**no Dhaka ground truth or correlation labels exist**, and **no source
licence/availability has been verified beyond the OSM research cell**. Source
integration and operational use remain **BLOCKED** pending the checks above.
Nothing in this document grants pilot or model activation.
