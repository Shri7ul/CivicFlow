# CivicFlow frontend

Next.js App Router frontend for CivicFlow. See the repository root `README.md`
for full setup and environment documentation.

Phase 1 through Phase 6 add:

- Supabase browser client using public configuration only.
- `/login`, `/signup`, and `/auth/callback` pages.
- Session restoration, token refresh, sign-out, and auth-aware navigation.
- Protected `/dashboard`, `/incidents/**`, `/map`, `/risk`, and `/decisions/**` routes with
  optimistic proxy redirects and a client-side auth guard.
- An incident queue, report form, detail view, inline editing, staff lifecycle
  actions, and an immutable history timeline.
- A MapLibre GL JS incident map with viewport bbox queries, native clustering,
  filters, marker selection, list synchronization, and a report location picker.
- Private evidence upload with progress/retry and signed preview URLs on the
  incident detail page.
- An explainable incident-intelligence panel with duplicate/related suggestions,
  staff-reviewed relationships, nearby infrastructure, potential impact paths,
  thresholds, and limitations.
- An H3 urban risk map with GeoJSON cells, resolution/window controls, legend,
  viewport filtering, top-cell drilldown, factor bars, trend/confidence, nearby
  asset exposure, and visible model limitations.
- A planning-only decision workspace for scenarios, response actions, explicit
  resource assumptions, bounded simulation results, target H3 overlays, and
  transparent strategy comparison.
- A profile/service error state when the FastAPI backend is unavailable.

Roles are assigned by the backend. The frontend never accepts a privileged role
from browser metadata and the service-role key must never be configured here.
MapLibre is dynamically imported on the client; map routes are still protected
by the client auth guard while the backend remains the authorization boundary.
Evidence bytes go through the backend multipart endpoint, never directly from
the browser to a privileged Storage credential.

## Commands

```powershell
cd frontend
npm install
npm run dev
npm run typecheck
npm run lint
npm test
npm run build
```

Copy `.env.example` to `.env.local` and set the public Supabase URL and anon key
to enable sign-in. Without those values the auth pages show a configuration
message instead of crashing.
