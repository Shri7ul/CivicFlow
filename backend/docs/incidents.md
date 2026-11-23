# Incidents API and lifecycle

Phase 2 adds authenticated incident reporting and a forward-only municipal
response workflow. The backend is the authorization boundary; RLS remains the
defense-in-depth layer for direct Supabase access.

## Visibility

- `CITIZEN`: list and detail include only incidents where `reporter_id` matches
  the caller's profile. Another Citizen's incident returns `404` (existence is
  not disclosed).
- `WORKER` and `ADMIN`: list and detail include the citywide queue.

## Endpoints

All endpoints require `Authorization: Bearer <Supabase access token>` and an
active profile.

| Method | Path | Roles | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/incidents` | active user | Report an incident |
| `GET` | `/api/v1/incidents` | active user | Scoped list with filters |
| `GET` | `/api/v1/incidents/{id}` | active user | Detail, lifecycle history, and evidence |
| `PATCH` | `/api/v1/incidents/{id}` | active user | Edit content under the rules below |
| `POST` | `/api/v1/incidents/{id}/status` | `WORKER`, `ADMIN` | Advance lifecycle |
| `GET` | `/api/v1/incidents/{id}/evidence` | active user | Evidence metadata on a visible incident |
| `POST` | `/api/v1/incidents/{id}/evidence` | active user | Upload 1–5 private images |
| `GET` | `/api/v1/incidents/{id}/evidence/{evidence_id}/url` | active user | Short-lived signed preview URL |
| `GET` | `/api/v1/departments` | active user | Active departments for assignment |

### Create

```json
{
  "title": "Blocked storm drain",
  "description": "Water is pooling across the road after every rain shower.",
  "category": "DRAINAGE",
  "severity": "HIGH",
  "latitude": 23.8103,
  "longitude": 90.4125,
  "address": "Road 12, Dhanmondi"
}
```

Coordinates are validated (`-90..90`, `-180..180`) and stored as a PostGIS
`geography(POINT,4326)`. The API returns WKT through `ST_AsText`, then exposes
`latitude`/`longitude` in JSON. New incidents are always `OPEN` and unassigned.
The reporter is never accepted from the request body.

### List filters

`page`, `page_size` (maximum 100), `status`, `category`, `severity`,
`department_id`, `q` (title/description/address search), and the optional
bounding box `min_latitude`, `min_longitude`, `max_latitude`, `max_longitude`.

Bounding-box filtering uses `ST_MakeEnvelope` + `ST_Intersects` against the
geography column and therefore requires PostgreSQL/PostGIS. The isolated SQLite
test dialect returns `400 spatial_filter_unsupported` rather than silently
ignoring the filter.

### Editing

- A Citizen may edit their own incident only while it is `OPEN`.
- A Worker or Admin may edit content until the incident is `CLOSED`.
- Editing after the allowed state returns `409 incident_not_editable`.
- Sending no fields returns `422 empty_update`.
- Updating only one coordinate preserves the other coordinate.
- Status, reporter, and department are not accepted by the content update
  schema (`extra="forbid"`).

### Lifecycle

```text
OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED
```

Additional allowed shortcut: `OPEN → IN_PROGRESS`.

- Any other transition returns `409 invalid_status_transition`.
- `ACKNOWLEDGED` and `IN_PROGRESS` require an active assigned department;
  otherwise the API returns `422 department_required`.
- A department can be selected in the same status request. An unknown or
  inactive department returns `422 invalid_department`.
- `RESOLVED` sets `resolved_at`.
- Every create and transition writes an immutable `incident_status_events` row
  with actor, previous status, new status, optional note, and timestamp.
- Citizens cannot call the status endpoint; they receive `403 insufficient_role`.

## Error codes

| Code | HTTP | Meaning |
| --- | --- | --- |
| `incident_not_found` | 404 | Missing or not visible to the caller |
| `incident_not_editable` | 409 | Content edit blocked by lifecycle state |
| `invalid_status_transition` | 409 | Transition is not allowed |
| `department_required` | 422 | Assignment needed before acknowledgement/work |
| `invalid_department` | 422 | Department missing or inactive |
| `invalid_bbox` | 422 | Partial or inverted bounding box |
| `spatial_filter_unsupported` | 400 | Bounding box used on non-PostgreSQL test dialect |
| `empty_update` | 422 | PATCH contained no fields |
| `insufficient_role` | 403 | Citizen attempted a staff action |

## Database

Migration `0004_incident_lifecycle.py` creates `incident_status_events` with
foreign keys to `incidents` and `profiles`, a composite incident/created index,
an actor index, and CHECK constraints for the status values and no-op
transitions. RLS is enabled with a SELECT policy for the reporter, Workers, and
Admins. `anon` receives no grant; `authenticated` receives `SELECT` only. The
backend writes history with its trusted database connection.

## Not included in this goal

Evidence storage/upload, duplicate detection and clustering, MapLibre rendering,
risk scoring, infrastructure dependency analysis, scenario simulation, and
notification delivery remain future work. The current frontend uses validated
coordinate entry and does not claim a map view.
