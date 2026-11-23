# Incident intelligence

Phase 4 adds a deterministic, explainable intelligence layer on top of incident
operations. It is decision support, not an autonomous dispatcher:

- suggestions are computed on demand from existing records;
- every suggestion includes reasons, component signals, weights, and confidence;
- incidents are never merged, deleted, or reassigned by the engine;
- only a `WORKER` or `ADMIN` can persist a `CONFIRMED` or `DISMISSED` review;
- the API distinguishes geospatial association and inferred dependency potential
  from observed facts.

## Persistent model

Migration `0006_incident_intelligence.py` creates
`public.incident_relationships`:

| Column | Meaning |
| --- | --- |
| `incident_a_id`, `incident_b_id` | Canonical pair (`a < b`) with `RESTRICT` foreign keys |
| `relationship_type` | `RELATED`, `DUPLICATE`, or `CONTEXT` |
| `status` | `CONFIRMED` or `DISMISSED` |
| `confidence` | `NUMERIC(4,3)`, constrained to `0..1` |
| `signals` | Reviewer/engine explanation envelope (`JSONB`) |
| `note` | Optional review note (max 500 characters) |
| `reviewed_by`, `reviewed_at` | Review provenance |

A unique constraint on `(incident_a_id, incident_b_id, relationship_type)`
prevents reverse-pair duplicates. A self-relationship is rejected by both the
API and a CHECK constraint. Relationships are preserved if a reviewer profile is
deleted (`SET NULL`); deleting either incident is restricted while a review
exists.

## Candidate retrieval and scoring

The engine queries incidents within the configured related radius/time window,
using PostGIS `ST_DWithin` for bounded candidate retrieval on PostgreSQL. It
then computes authoritative WGS84 great-circle distance in Python, so SQLite
tests and PostgreSQL use the same scoring inputs.

Five weighted components produce confidence:

| Signal | Weight | Component |
| --- | --- | --- |
| Spatial proximity | 0.32 | Linear decay to zero at the duplicate radius |
| Temporal proximity | 0.18 | Linear decay over the duplicate time window |
| Text similarity | 0.23 | 65% normalized token Jaccard + 35% sequence ratio |
| Category compatibility | 0.13 | 1.0 same category, 0.55 configured related category |
| Severity similarity | 0.04 | 1.0 minus rank difference / 3 |
| Lifecycle status | 0.10 | Same status 1.0; both active 0.8; both terminal 0.7; otherwise 0.25 |

Duplicate candidates additionally require:

- distance at or below `INTELLIGENCE_DUPLICATE_RADIUS_M`;
- report time within `INTELLIGENCE_DUPLICATE_WINDOW_HOURS`;
- same or configured-related category;
- text score at or above `INTELLIGENCE_DUPLICATE_TEXT_THRESHOLD`;
- confidence at or above `INTELLIGENCE_DUPLICATE_CONFIDENCE_THRESHOLD`.

Related suggestions use the wider radius/window and the related confidence
threshold, excluding items already classified as duplicates. The default values
are in `README.md` and `backend/.env.example`. They are configuration, not
hard-coded business truth.

Text normalization removes common stopwords, punctuation, and very short tokens
and blends token overlap with sequence similarity. It is intentionally simple
and auditable; it is not a semantic model and does not understand every synonym.

## Infrastructure context

`GET /api/v1/infrastructure/assets` returns active assets from
`infrastructure_assets`, authenticated only. The intelligence response adds
nearby assets within `INTELLIGENCE_INFRASTRUCTURE_RADIUS_M`. Distance is
computed with PostGIS geography (metres) on PostgreSQL. Candidate retrieval uses
a conservative degree bound against the existing WGS84 GIST index, then applies
the authoritative geography distance; this avoids treating a metre radius as
degrees.

The repository seed contains **development-only** assets (Central Avenue, North
Drain Main, City General Hospital, Riverbank Shelter, and others) with
Dhaka-area coordinates. No authoritative municipal asset feed is configured.
The API reports this limitation rather than implying that seed data is real
operational infrastructure.

## Impact paths

`potential_impacts` is a foundation for dependency-aware analysis, not a
prediction engine:

- depth `0` entries are `GEOSPATIAL_ASSOCIATION`: the asset is near the report.
- downstream entries follow `dependency_edges` and are `INFERRED_POTENTIAL`.
- confidence decays with each edge (`parent × edge.strength × 0.85`), capped
  below 1.
- traversal is bounded by `INTELLIGENCE_IMPACT_DEPTH` and
  `INTELLIGENCE_IMPACT_LIMIT`.
- every inferred path states that it is an inferred dependency association, not
  an observed impact.

No service-outage observation, damage report, sensor feed, or real-world
cascade prediction is claimed.

## API

```text
GET  /api/v1/incidents/{incident_id}/intelligence
GET  /api/v1/incidents/{incident_id}/relationships
POST /api/v1/incidents/{incident_id}/relationships
GET  /api/v1/infrastructure/assets
```

The intelligence response contains:

- `duplicate_candidates` and `related_candidates` with incident summaries,
  distance, time delta, text similarity, confidence, reasons, and signals;
- `confirmed_relationships` visible to the caller;
- `infrastructure` with distance and dependency count;
- `potential_impacts` with path, depth, type, confidence, and rationale;
- `thresholds` and `limitations` so clients can explain the result.

Relationship review payload:

```json
{
  "other_incident_id": "00000000-0000-0000-0000-000000000000",
  "relationship_type": "DUPLICATE",
  "status": "CONFIRMED",
  "confidence": 0.82,
  "signals": {"source": "incident_intelligence"},
  "note": "Same drain and time window."
}
```

Review is restricted to `WORKER`/`ADMIN`. Re-review updates the same canonical
row; concurrent conflicting writes return `409 relationship_conflict`. A citizen
attempting review receives `403 insufficient_role`. Self-links return
`422 self_relationship`.

## Privacy and authorization

- Citizens see only their own incidents and their own evidence.
- Candidate retrieval applies the same incident visibility rule before scoring.
- A Citizen's relationship list hides any relationship whose other incident is
  not theirs.
- Hidden incidents return opaque `404 incident_not_found` responses.
- The relationship table has RLS and SELECT-only grants for `authenticated`;
  writes stay backend-only under the service role.
- No service-role key or JWT is exposed to the browser.

## Verification

Automated tests cover:

- pure distance/text/format helpers;
- duplicate and related scoring with explanations;
- same-location/different-text non-duplicate behavior;
- cross-Citizen candidate privacy;
- staff-only review, unique persistence, dismissal updates, self-review rejection;
- infrastructure proximity, dependency traversal, and inferred labels;
- old candidates outside the duplicate time window;
- SQLite constraints/unique pairs and offline PostgreSQL migration rendering.

Live validation used disposable real Auth users, incidents, assets, and a
dependency edge over HTTP. It verified duplicate suggestions, cross-Citizen
privacy, staff review, opaque 404s, PostGIS proximity, inferred-impact labeling,
and cleanup to zero. Headless Chrome verified the rendered panel, explanation
details, empty states, thresholds, and limitations.

## Known limitations

- No NLP/embedding model; text matching is lexical.
- No automatic merging, cluster assignment, or incident deletion.
- No authoritative municipal asset dataset or live sensor feed.
- Phase 4 does not itself score risk or create H3 cells; Phase 5 provides the
  separate risk engine. Scenario simulation and notification delivery remain
  future work.
- Dependency paths reflect seeded/loaded graph edges only.
- Impact confidence is a transparent heuristic, not a calibrated probability.
