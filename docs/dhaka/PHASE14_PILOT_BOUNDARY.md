# Phase 14 — Dhaka Pilot Boundary Verification

Status: **IMPLEMENTED (workflow) / NO APPROVED BOUNDARY — pilot BLOCKED**

## 1. Problem

The registered `BD-DHAKA` rectangle (`90.30, 23.68 – 90.50, 23.90`) and the
bounded OSM research cell (`90.390, 23.780 – 90.410, 23.800`) are **screening
envelopes**, not DNCC/DSCC/ward boundaries. Selecting a pilot area from OSM
completeness alone would be evidence-free and is explicitly prohibited.

## 2. Implemented workflow

`backend/app/phase14/boundaries.py` plus the `pilot_boundaries` and
`pilot_boundary_events` tables (migration `0024_phase14_pilot`) implement:

| Requirement | Implementation |
| --- | --- |
| Geographic boundary source | `source_owner`, `source_name`, `source_url`, `source_type` |
| Source authority | `source_type`: OFFICIAL_ADMINISTRATIVE, AUTHORITATIVE_PUBLIC, PARTNER_PROVIDED, OSM_RESEARCH, UNKNOWN |
| Source date / version | `source_date`, `boundary_version` |
| CRS | `crs` restricted to WGS84 variants (`EPSG:4326`, `CRS84`, `WGS84`) |
| Coordinate validation | numeric, finite, `-180..180` / `-90..90`, non-empty, checked at registration |
| Geometry validation | GeoJSON polygon, ≥4 positions per ring, closed rings, non-zero area, declared bbox matches geometry extent, extent inside registered context |
| Provenance | `provenance_note`, `license_note`, append-only events with actor and timestamp |
| Integrity hash | SHA-256 of a canonical document (source identity, date, version, CRS, geometry, bbox), stored as `integrity_sha256` |
| Human approval | distinct submitter → verifier → approver; approval requires an `approval_reference` and rationale |
| Geographic scope restriction | context is derived server-side from the bbox; client-supplied context that disagrees is rejected |
| Status | UNVERIFIED → PENDING_REVIEW → VERIFIED → APPROVED; REJECT returns to UNVERIFIED with a reason |

No boundary is auto-created, auto-verified or auto-approved. OSM_RESEARCH and
PARTNER_PROVIDED sources cannot be approved as authoritative through this API.

## 3. Verification procedure (to be executed by humans)

1. Identify an authoritative boundary publisher (e.g. a city corporation ward
   register). Source identity, version, date, licence and access permission
   must be recorded before acquisition.
2. Acquire the boundary through the authorised channel. Record where the file
   came from, who supplied it, and the exact retrieval timestamp.
3. Convert to GeoJSON EPSG:4326 without dissolving or simplifying topology
   silently; document any transformation.
4. Register through `POST /api/v1/governance/phase14/boundaries`.
5. Submit, verify and approve through three distinct administrator identities.
   Approval must cite the human decision reference.
6. Re-read `integrity_sha256` and confirm it matches the archived source file.
7. Link the approved boundary to a specific pilot before any activation request.

## 4. Current state

| Item | Status |
| --- | --- |
| Boundary workflow implemented | IMPLEMENTED / AUTOMATED-TESTED |
| Authoritative Dhaka boundary acquired | BLOCKED |
| Boundary approved by a human | BLOCKED (0 records) |
| Pilot area selected from an approved boundary | BLOCKED |
| Boundary integrity hash verified against an archived source | NOT_ASSESSED |

The final Phase 14 gate reads only persisted APPROVED boundaries; the gate
remains `NOT_READY` until an approved boundary exists.
