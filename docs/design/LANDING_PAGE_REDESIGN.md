# CivicFlow — Production Landing Page Redesign

Date: 2026-11-26. Scope: public homepage and its dedicated presentation layer.
No backend, database, migration, RLS or authentication-policy changes were made.

## 1. Baseline audit findings

The audit was performed before any edits. Evidence is in
`docs/audit/FULL_PROJECT_AUDIT.md` and `docs/audit/BASELINE_VERIFICATION.md`.

- The previous homepage (`frontend/src/app/page.tsx`) was a server component
  built around a phase badge, a long 17-item "foundation" checklist, a
  development-status panel, an architecture section and a sticky live
  connectivity card. It read like a developer project showcase.
- It carried phase-oriented copy (`Phase 14` locally, while the deployed build
  was previously confirmed to still show `Phase 13` / `Phase 5` / `35 tables`),
  a "Complete" badge beside research-oriented caveats, and a localhost-based
  health URL when the API base URL was unset.
- `SiteHeader` and `SiteFooter` are shared by every protected page and the auth
  shell. Repurposing them for a marketing navigation would have broken the
  application shell, so they were left untouched.
- Live map components (`IncidentMapView`, `RiskMapView`) call `useAuth` and fire
  authenticated API requests on mount. They are not safe to embed in a public
  hero and were not reused.
- The test environment has no DOM testing library; component tests render to
  static markup with `renderToStaticMarkup`.
- No `page.test` or `auth-nav.test` existed, so homepage copy and link targets
  had no regression net.

## 2. Design rationale

The page was rebuilt around a restrained dark product palette and a
product-screenshot composition rather than a generic AI/startup template.

| Token | Value | Use |
|---|---|---|
| Background | `#05080B` | Page canvas |
| Surface | `#0B1118` | Cards, panels, preview chrome |
| Elevated surface | `#101824` | Hover and nested surfaces |
| Border | `#1B2733` | Fine separators |
| Primary accent | `#10B981` | Emphasis, active states, primary CTA |
| Secondary accent | `#22D3EE` | Risk/intelligence tone, gradient end |
| Text | `#F1F5F9` | Primary copy |
| Muted text | `#94A3B8` | Supporting copy |

Design choices:

- One headline gradient restricted to text; no large decorative glow blocks.
- Fine 1px borders and small radii (`rounded-lg` / `rounded-xl`); no giant
  rounded cards.
- A single restrained grid backdrop and top glow, reused from the existing
  `.site-grid` / `.site-glow` styles.
- No fabricated statistics: no accuracy percentages, citizen counts, incident
  volumes or "AI prediction" claims appear anywhere on the page.
- The status panel states plainly that pilot activation is **not active** and
  that verification is local, not production E2E.

## 3. Component structure

New dedicated directory `frontend/src/components/landing/`:

| File | Responsibility |
|---|---|
| `landing-content.ts` | Single source of truth for copy, section ids, links, capability/workflow/architecture/governance/status data; testable without rendering. |
| `landing-icons.tsx` | Small meaningful SVG icon set; no new dependency. |
| `landing-header.tsx` | Sticky public header, responsive mobile menu, `IntersectionObserver` scroll-spy active state. |
| `landing-footer.tsx` | Product/status/access links, copyright, illustrative-preview disclosure. |
| `product-preview.tsx` | Static hero visualization and larger reconstructed workspace preview. |
| `landing-sections.tsx` | Capabilities, workflow, architecture, trust/governance, pilot status, final CTA. |
| `landing-content.test.ts` | Link integrity, section counts and copy-honesty assertions. |

`frontend/src/app/page.tsx` is now a thin composition of those sections and no
longer contains inline content arrays.

## 4. Sections implemented

1. **Navigation** — brand + "Urban Response Intelligence" subtitle; centre
   links Platform / Intelligence / Architecture / Pilot Status; right-side
   auth actions; sticky, keyboard accessible, active section underline.
2. **Hero** — required headline and value proposition, "Explore the platform"
   and "View architecture" CTAs, assurance markers, and a static product
   visualization with an incident map, markers, queue rows, status pills and
   H3 risk bands.
3. **Capabilities** — "An integrated urban response workspace": six
   capability tiles in a varied 6/3/3 then 4/4/4 layout, each describing an
   implemented capability and its research boundaries.
4. **Workflow** — Report → Locate → Analyze → Plan → Review as a five-step
   row with arrows; each step describes the real pipeline and explicitly
   states that no automated dispatch or real-world execution occurs.
5. **Platform preview** — reconstructed authenticated workspace with sidebar,
   filters, map, incident queue and explainable risk components.
6. **Architecture** — Next.js/TypeScript/MapLibre, FastAPI/RBAC,
   PostgreSQL/PostGIS/Alembic, Supabase infrastructure. Only technologies
   present in the repository are named.
7. **Trust and governance** — three clearly separated tiers: Implemented,
   Research-oriented, Externally dependent.
8. **Pilot status** — honest status rows plus the existing `BackendStatus`
   component, which performs a real browser GET to the configured health
   endpoint and is labelled as such.
9. **Final CTA** — "Bring urban response workflows into one workspace." with
   Create account and Explore platform actions.
10. **Footer** — CivicFlow branding, product/status/access links, copyright,
    and a disclosure that interface previews are illustrative.

## 5. Reused components and navigation changes

- `AuthNav` was extended with an additive `minimal` prop for the public
  header; the full app-shell navigation is unchanged. Its sign-out control was
  extracted into one shared internal component so no logic is duplicated.
- `BackendStatus` is reused in the status section for a genuine, non-simulated
  connectivity check. It performs an unauthenticated GET only; no database
  writes or pilot actions.
- `SiteHeader` / `SiteFooter`, live maps, evidence gallery, validation
  dashboard and all other authenticated components were deliberately not
  reused on the public page.
- Public navigation targets are only `#platform`, `#intelligence`,
  `#architecture`, `#pilot-status`, `/login` and `/signup`. The previous
  `/pilot` link (a protected route that redirects citizens to login) was
  removed from the public header and replaced with the in-page status section.
- Final CTA and all footer links point to existing public routes or anchors.

## 6. Mock data disclosure

The two product previews are static CSS/SVG illustrations. Their example
incident ids, counts, queue rows, markers and risk bands are **not** live data.
Every preview is labelled "Illustrative preview" in the rendered UI, the
workflow preview carries an explicit caption, and the footer contains a global
disclosure. No API request, database read/write or auth action is triggered by
the illustrations.

## 7. Responsive behavior

Verified with a real Chromium browser against the local production build at
1440×900, 1280×800, 1024×768, 768×900, 390×844 and 360×780.

- `document.documentElement.scrollWidth === clientWidth` at every viewport;
  no horizontal overflow.
- Navigation switches from centre links to a hamburger menu below `lg`; the
  menu exposes `aria-expanded` / `aria-controls`, closes on link selection and
  scrolls to the target anchor.
- Hero collapses from two columns to one; product preview hides its queue
  panel on narrow screens but keeps the map and example status strip readable.
- Capability grid varies from 12-column desktop layout to 2-column tablet and
  1-column mobile; workflow stepper becomes a vertical list on mobile.
- Headline scales from 2.4rem to 3.8rem with no clipping or overlap.

## 8. Test results

Executed locally on 2026-11-26:

| Check | Result |
|---|---|
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm test` | 37 files, 148 tests passed (10 new landing tests) |
| `npm run build` | Passed; `/` prerendered as static content |
| Prerendered route audit | All four section ids present exactly once; all anchors/routes resolve; zero stale phase/table/fake-stat strings |
| Browser page errors / console errors | None at any tested viewport |
| Browser interaction | Mobile menu open/close and anchor navigation verified |

A build-time issue was found and fixed: Next.js 16 rejects `new Date()` during
prerender, so the footer year is now a static exported constant.

A layout defect found during browser review was fixed: the workflow stepper
initially used 14 column spans in a 9-column grid and wrapped into two rows;
it now renders as one row of five steps on large screens.

## 9. Remaining limitations

- Verification was against the **local production build**. No Vercel deploy
  was performed, so the live public URL still serves the previous build until
  an operator redeploys `main`.
- No production account was used; authenticated navigation states were not
  exercised against live Supabase. The `minimal` auth branch is covered by the
  existing auth context logic and was not browser-tested while signed in.
- Screenshots were captured locally with `agent-browser` for review but are
  not committed as project artifacts.
- The live `BackendStatus` panel reflects browser-to-API reachability only; it
  is not a database migration, RLS or pilot-readiness check.
- This is a public-page redesign only. The in-app dashboards retain their
  existing functional layouts.
