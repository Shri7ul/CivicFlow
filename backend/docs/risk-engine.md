# Urban risk engine (Phase 5)

CivicFlow's risk engine turns authorized incident observations into bounded H3
cells, compares them with the immediately preceding window, and adds inferred
infrastructure exposure. It is **configuration-driven, deterministic, and
explainable**. It is not a prediction, a confirmed impact assessment, or a
replacement for field verification.

## Architecture

```text
incidents (PostGIS) ──bounded query/bbox──┐
                                          ├─ H3 aggregation ── factor scoring ── API
infrastructure_assets + dependency_edges ─┘        │
                                                   ├─ current/previous trend
                                                   └─ privacy + authorization

staff POST /risk/runs ── risk_model_runs ── risk_cell_snapshots
```

| Module | Responsibility |
| --- | --- |
| `app/risk/config.py` | Validated `RiskConfig`, factors, bands, version/hash |
| `app/risk/scoring.py` | Aggregation, duplicate adjustment, factor normalization, trend |
| `app/risk/geo.py` | Portable haversine/WKT distance and bbox checks |
| `app/risk/exposure.py` | Asset proximity, type/criticality weighting, provenance |
| `app/risk/engine.py` | H3 cells, temporal windows, bounded querying, limitations |
| `app/risk/persistence.py` | Staff run and snapshot persistence |
| `app/risk/serialization.py` | API/GeoJSON shaping |
| `app/api/v1/endpoints/risk.py` | Authenticated risk endpoints and validation |

## Configuration

Settings are validated at startup. Factor weights must define exactly the nine
configured factors and sum to `1.0`; severity/category weights must define every
enum member; thresholds must be strictly ascending inside `(0, 100)`; and
resolution/window bounds must be ordered. Configuration mappings are frozen to
prevent post-validation mutation. The effective model is exposed at `GET /api/v1/risk/config`, and
`config_hash` is stored on every cell result and snapshot.

Default `risk-v1` weights:

| Factor | Weight | Meaning |
| --- | ---: | --- |
| Severity | 0.24 | Recency-weighted severity prior |
| Adjusted density | 0.13 | Log-scaled count after confirmed-duplicate adjustment |
| Spatial concentration | 0.07 | Within-cell clustering relative to the H3 edge |
| Recency | 0.14 | Exponential age decay, 72-hour half-life by default |
| Active share | 0.08 | OPEN / ACKNOWLEDGED / IN_PROGRESS share |
| Category consequence | 0.08 | Transparent category prior, not empirical impact |
| Temporal trend | 0.06 | Current vs previous-period count change |
| Infrastructure exposure | 0.14 | Proximity/type/criticality exposure |
| Dependency context | 0.06 | Dependency links touching nearby assets |

Every factor response includes `raw_value`, `normalized`, `weight`,
`contribution`, `available`, and an explanation. Unavailable factors are
excluded and remaining weights are renormalized; reported contributions use the
same effective weights and sum to the returned composite `risk_score`.
`incident_activity_score` and the composite `risk_score` are reported separately.

Only **WORKER/ADMIN-confirmed DUPLICATE relationships** adjust the incident
count. Unresolved suggestions never change risk. Duplicate clusters are
deduplicated globally across the loaded current and previous windows before H3
assignment, so a cluster cannot be counted once per window or once per adjacent
cell. The adjustment is explicit in `incident_count`,
`adjusted_incident_count`, and `removed_duplicates`.

## Spatial and temporal behavior

- H3 resolutions are configurable (default 7–10). Boundaries are returned as
  GeoJSON polygons and WKT; centers drive infrastructure proximity.
- Current and immediately preceding equal-length windows are loaded in one
  bounded query. The previous window support is used for trend comparison.
- Trend classification is `INCREASING`, `DECREASING`, `STABLE`, or
  `INSUFFICIENT_DATA`. It requires full previous-window coverage and the
  configured combined history; sparse or incompletely covered cells never
  receive a confident direction and explain why.
- On PostgreSQL, bounding boxes use `ST_Intersects` against the incident
  geography with a cast envelope that remains sargable for the GIST index.
  Asset proximity is computed with portable WGS84 distance after indexed
  candidate filtering; POLYGON assets containing the cell centre return zero
  distance. SQLite supports the same scoring for tests.
- Requests over the incident or cell caps fail with a clear error instead of
  silently truncating. Narrow the bbox, choose a coarser resolution, or shorten
  the window.

## API

All endpoints require authentication. Risk snapshots additionally require
WORKER/ADMIN.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/risk/config` | Effective model, weights, bands, limitations |
| GET | `/api/v1/risk/cells` | Paginated cell results; `format=geojson` |
| GET | `/api/v1/risk/summary` | Cell/category/trend/exposure summary |
| GET | `/api/v1/risk/cells/{h3_cell_id}` | Cell detail + authorized incident briefs |
| GET | `/api/v1/risk/trends` | Current/previous comparison per cell |
| GET | `/api/v1/risk/infrastructure-exposure` | Exposure cells/assets summary |
| POST | `/api/v1/risk/runs` | Persist a staff run and snapshots |
| GET | `/api/v1/risk/runs` | List persisted runs |

Common query parameters: `resolution`, `window` (`current`, `24h`, `7d`,
`30d`; `current` uses the configured default window) or `window_hours`,
`min_latitude`/`min_longitude`/`max_latitude`/`max_longitude`, `min_score`,
`category`, `limit`, and `offset`.

Error codes include `invalid_resolution`, `invalid_window`, `invalid_limit`,
`invalid_bbox`, `risk_query_too_large`, `risk_too_many_cells`,
`risk_cell_not_found` (opaque for hidden/invalid cells), and
`insufficient_role` for snapshot operations.

## Privacy and authorization

- Citizens receive only cells meeting `RISK_PRIVACY_MIN_INCIDENTS`; suppressed
  counts are reported in `privacy.suppressed_cells`.
- Citizen trend objects are withheld when either comparison window is below the
  privacy minimum; `/risk/trends` omits those cells entirely. This prevents a
  low-count comparison window from leaking through a visible current cell.
- Cell detail returns only incident briefs the caller is authorized to see.
  A suppressed cell returns an opaque 404.
- Aggregate cells never include reporter identities. Cross-Citizen incident
  data remains hidden even when both reports contribute to the same aggregate.
- Staff snapshots are protected by RLS and are not directly insertable through
  the authenticated database role; all writes go through the API.
- `risk_model_runs` and `risk_cell_snapshots` store model version, config hash,
  window, resolution, score, category, confidence, factors, and trend context.

## Interpretation limits

- Risk is decision support, not a prediction or confirmed real-world impact.
- Infrastructure exposure is **geospatial association**. Nearby assets and
  dependency links do not prove an outage, service loss, or cascade.
- Dependency paths in Phase 4 incident intelligence remain labeled
  `INFERRED_POTENTIAL`; Phase 5 exposure uses the same conservative language.
- Category, severity, and infrastructure type weights are transparent model
  priors, not validated outcome estimates.
- The repository asset/dependency dataset is development data unless a
  deployment loads an authoritative municipal dataset. `dataset` metadata
  reports authoritative/development counts and asset-limit truncation.
- Sparse or incompletely covered history reduces confidence and can make trends
  unavailable. A trend is not asserted until the full previous window is
  observable and the combined count meets the configured minimum.
- Minimum-count suppression applies to total cell counts. Severity/category
  sub-distributions inside an otherwise eligible cell are aggregate model
  context and are not independently suppressed; they do not identify reporters.
- H3 cell boundaries are analysis units, not administrative or legal boundaries.
