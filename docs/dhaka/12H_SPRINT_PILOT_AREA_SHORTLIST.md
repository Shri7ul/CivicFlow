# 12-Hour Sprint — Pilot Area Shortlist

This is a **shortlist for human review only**. No area has been selected, approved, or activated.

## Evaluation inputs

- Official BGISP city-corporation boundaries and 164 DNCC/DSCC ward candidates.
- HDX COD-AB v03 DNCC/DSCC boundaries.
- geoBoundaries ADM4 candidates inside the COD-AB city polygons.
- Existing bounded Dhaka OSM research cell: 552 Overpass elements, 511 normalized records, research-only.
- World Bank national urban population: context only.

## Candidate 1 — Dhaka North City Corporation (preferred for evidence density, not selected)

| Attribute | Value |
|---|---|
| Official identity | `city_geo_code=302625`; COD-AB `BD30262500` |
| BGISP bbox | `[90.328907237, 23.738892653, 90.490360489, 23.900692811]` |
| Official ward features | 76 |
| geoBoundaries ADM4 candidates | 59; 49 ward-named; 40 unique ward labels |
| Existing OSM research elements inside polygon | 552 of 552 |
| Strengths | Two authoritative/official boundary sources agree within `9.82e-7` degrees; densest existing research context; official ward layer available. |
| Weaknesses | BGISP license/vintage unconfirmed; OSM records are road/bridge-like context and are not ground truth; duplicate/part ward names. |
| Status | **Candidate only**. |

## Candidate 2 — Dhaka South City Corporation

| Attribute | Value |
|---|---|
| Official identity | `city_geo_code=302620`; COD-AB `BD30262000` |
| BGISP bbox | `[90.351719200, 23.669186621, 90.511980260, 23.785339723]` |
| Official ward features | 88 |
| geoBoundaries ADM4 candidates | 79; 66 ward-named; 60 unique ward labels |
| Existing OSM research elements inside polygon | 0 |
| Strengths | Two boundary sources agree within `3.90e-6` degrees; largest official ward set; complete official ward layer available. |
| Weaknesses | No existing OSM research evidence inside the polygon; higher field-validation burden; BGISP license/vintage unconfirmed. |
| Status | **Candidate only**. |

## Candidate 3 — Combined DNCC + DSCC

| Attribute | Value |
|---|---|
| Official ward features | 164 |
| geoBoundaries ADM4 candidates | 138 |
| Combined extent | Approximately `[90.328907237, 23.669186621, 90.511980260, 23.900692811]` |
| Strengths | Complete city-corporation coverage; useful for a later comparative phase. |
| Weaknesses | Larger and operationally more complex than a bounded initial pilot; mixes two corporations and 164 wards. |
| Status | **Not recommended for an initial bounded pilot without explicit human authorization.** |

## Excluded candidates

| Candidate | Reason |
|---|---|
| Nominatim DNCC office polygon | Office footprint, not an administrative boundary. |
| Existing OSM research cell | Arbitrary bounded research query, not a legal or administrative boundary. |
| RAJUK/NSDI/GeoDASH/data.gov.bd areas | No verifiable downloadable boundary evidence obtained. |
| Historical EO4SD flood proxy areas | Event-specific historical products, not current civic evidence. |

## Recommended human decision path

1. Choose **one** corporation (DNCC or DSCC) before choosing wards.
2. If evidence density is the priority, DNCC has the strongest existing research context; if field-team access and ward coverage are the priority, DSCC has the larger official ward set.
3. Select a small contiguous ward cluster from the official BGISP ward layer.
4. Record boundary source, license confirmation, verifier, approver and field-validation plan in the existing Phase 14 `PilotBoundary` workflow.
5. Do not treat this shortlist as approval; no pilot is active.

## Non-promotion rule

No OSM feature, ADM4 polygon, official ward polygon, World Bank value or model prediction has been promoted to a verified incident or ground-truth record.
