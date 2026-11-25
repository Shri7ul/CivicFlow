# Phase 14 — Dhaka Evidence Acquisition and Provenance

Status: **INTAKE WORKFLOW IMPLEMENTED / NO AUTHORIZED DHAKA CIVIC DATA ACQUIRED**

## 1. Source categories assessed (not acquired)

The following are candidate source categories only. Availability, authority,
licence, endpoint and access permission are **NOT_ASSESSED** unless an
authorized dataset is registered through the workflow below. No URL is asserted
for any of them.

| Category | Owner (to be verified) | Data possible | Current status |
| --- | --- | --- | --- |
| DNCC | Dhaka North City Corporation | Ward boundaries, civic works, local complaints | NOT_ASSESSED |
| DSCC | Dhaka South City Corporation | Ward boundaries, civic works, local complaints | NOT_ASSESSED |
| RAJUK | Rajdhani Unnayan Kartripakkha | Development plans, land-use layers | NOT_ASSESSED |
| BBS | Bangladesh Bureau of Statistics | Census/ward demographics | NOT_ASSESSED |
| BMD | Bangladesh Meteorological Department | Rainfall/weather observations | NOT_ASSESSED |
| WASA | Dhaka WASA | Water supply and drainage context | NOT_ASSESSED |
| BWDB | Bangladesh Water Development Board | River/flood data | NOT_ASSESSED |
| DDM | Department of Disaster Management | Hazard and disaster records | NOT_ASSESSED |
| Community / field observations | Verified partner or trained observer | Structured field observations | Workflow implemented; no operational records |
| OpenStreetMap | OpenStreetMap contributors | Community-mapped infrastructure context | One bounded research acquisition from Phase 12; not authoritative incident ground truth |

## 2. Implemented registration contract

`backend/app/phase14/datasources.py`, `PilotDataSource` (migration `0024`) and
`POST /api/v1/governance/phase14/data-sources` require:

source identity, owner, dataset name/description, geographic scope, acquisition
method, optional public HTTP(S) endpoint, licence note and licence reference,
timestamp note, update frequency, data-quality note, schema version, provenance
note, raw SHA-256, normalized SHA-256, coverage note, missing-data note,
confidence note and limitations.

Controls:

- Registration **never** yields `AUTHORIZED`. New rows are `UNAUTHORIZED` or
  `RESEARCH_ONLY`.
- A research-classified source cannot be promoted to operational authorization
  by this API. OSM stays research context.
- Authorization requires a distinct administrator, both hashes, a licence
  reference, documented limitations/quality and an authorization reference.
- Endpoints are validated as public HTTP(S) URLs; loopback/private/link-local
  hosts and metadata-style hostnames are rejected (SSRF boundary).
- The registration endpoint **does not download anything**. It records intent
  and provenance; acquisition remains a separate authorized operation.

## 3. Provenance rules

1. Retain the raw bytes and a SHA-256 of the raw file before normalization.
2. Normalize deterministically and record a SHA-256 of the canonical form.
3. Record source owner, retrieval time, licence, schema version and coverage.
4. Record what is missing and what is uncertain; absence must never be filled
   with an assumed value.
5. Keep synthetic fixtures out of operational evidence; they may only be
   classified as `RESEARCH_ONLY` or `SYNTHETIC`.
6. Never represent NYC research data as Dhaka evidence.

## 4. Current state

| Item | Status |
| --- | --- |
| Registration/provenance infrastructure | IMPLEMENTED / AUTOMATED-TESTED |
| Authorized authoritative Dhaka civic dataset | BLOCKED (0 registered) |
| Access authorization evidence | BLOCKED |
| Raw/normalized hashes for a Dhaka civic dataset | BLOCKED |
| Coverage, freshness and quality assessment | NOT_ASSESSED |
| Live acquisition against an external system | NOT_ASSESSED |

The final gate requires at least one fully documented AUTHORIZED source; it is
currently unmet.
