# Spatial incident API and map

Phase 3 reuses the Phase 2 incident list endpoint for all map queries. The map
does not download a full dataset and filter in the browser; the current viewport
and every active filter are sent to PostgreSQL.

## Viewport query

`GET /api/v1/incidents` accepts:

| Parameter | Type | Notes |
| --- | --- | --- |
| `min_latitude`, `min_longitude` | number | South-west corner, WGS84 |
| `max_latitude`, `max_longitude` | number | North-east corner, WGS84 |
| `status` | enum | `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED` |
| `category` | enum | Incident category |
| `severity` | enum | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `department_id` | UUID | Assigned department |
| `q` | string | Title/description/address search |
| `page`, `page_size` | integer | Defaults `1`, `20`; maximum page size `100` |

All four bounds are required for a spatial query. The backend validates the
envelope and uses PostGIS `ST_MakeEnvelope` + `ST_Intersects` against the
geography location. SQLite tests return `400 spatial_filter_unsupported` rather
than silently ignoring a spatial filter.

Visibility is applied before filters: a Citizen only sees their own reports;
Workers and Admins see the citywide queue. An invalid/incomplete bbox returns
`422 invalid_bbox`.

## Frontend map

- `frontend/src/app/map/page.tsx` is a protected route.
- `frontend/src/components/map/incident-map.tsx` dynamically imports MapLibre
  GL JS in an effect, so SSR does not touch `window`.
- `frontend/src/lib/map.ts` centralizes the Dhaka default viewport, OSM raster
  style, severity/status/category encodings, and GeoJSON conversion.
- The map is a single GeoJSON source with native `circle`/`symbol` layers. No
  one-DOM-marker-per-incident rendering is used.
- Cluster clicks call `getClusterExpansionZoom`; point clicks select an incident
  and show a preview with a detail link.
- The viewport `moveend` event updates a bbox state. A 300 ms debounce plus
  `AbortController` prevents stale responses from replacing newer results.
- Filters are combined server-side; the list and map share the same selected
  incident. The list is also the accessible alternative to canvas interaction.
- The report form adds a MapLibre click picker in addition to manual coordinates
  and browser geolocation.

## Encoding and limits

| Visual channel | Meaning |
| --- | --- |
| Fill color/radius | Severity (critical/high/medium/low) |
| Ring color | Lifecycle status |
| Abbreviation label | Category (`RD`, `DR`, `SA`, `UT`, `PS`, `HL`, `EN`, `OT`) |
| Cluster circle/label | Number of incidents in the cluster |

The default viewport is central Dhaka (`90.4125, 23.8103`, zoom `11.5`). List
queries request at most 100 features per viewport; the UI reports when the
server total exceeds the rendered page.

OSM raster tiles are used in this phase. Attribution is provided by MapLibre's
attribution control. Tile availability/usage policy must be reviewed before a
production deployment with high traffic.
