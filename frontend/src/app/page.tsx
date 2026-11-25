import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { BackendStatus } from "@/components/status/backend-status";
import { siteConfig } from "@/config/app";
import { getApiBaseUrl } from "@/lib/api/client";

const foundationItems = [
  {
    title: "Incident reporting",
    description:
      "Validated coordinates, category, severity, description, and optional address on a real map-ready location.",
  },
  {
    title: "Visibility-scoped queue",
    description:
      "Citizens see their own reports; Workers and Admins see the citywide incident queue.",
  },
  {
    title: "Response lifecycle",
    description:
      "Acknowledge, assign, start work, resolve, and close with an immutable status history.",
  },
  {
    title: "PostGIS spatial data",
    description:
      "WGS84 geography storage, GIST indexes, and live bounding-box filtering.",
  },
  {
    title: "Interactive incident map",
    description:
      "MapLibre GL JS with viewport queries, native clustering, severity/status/category encoding, and list synchronization.",
  },
  {
    title: "Private photo evidence",
    description:
      "Validated JPEG/PNG/WebP uploads, private Supabase Storage, and short-lived signed previews.",
  },
  {
    title: "Explainable incident intelligence",
    description:
      "Deterministic spatial, temporal, category, text, and severity signals with reasons, confidence, and explicit limitations.",
  },
  {
    title: "Infrastructure and impact context",
    description:
      "PostGIS asset proximity and dependency-aware impact foundations that distinguish spatial association from inferred potential.",
  },
  {
    title: "H3 urban risk cells",
    description:
      "Versioned, configuration-driven risk bands with explainable severity, density, recency, status, category, and exposure factors.",
  },
  {
    title: "Risk map and trends",
    description:
      "MapLibre H3 polygons, resolution/window controls, previous-period trends, confidence, and staff-only persistent snapshots.",
  },
  {
    title: "Decision scenarios",
    description:
      "Staff-only response scenarios with explicit actions, dependencies, budgets, and resource constraints.",
  },
  {
    title: "Planning simulation and strategy comparison",
    description:
      "Bounded scheduling heuristics show reduction, coverage, cost, and blocked actions without dispatching or reserving anything.",
  },
  {
    title: "Model governance and evaluation",
    description:
      "Registered configuration hashes, ADMIN activation audit, and labelled metrics with explicit synthetic-fixture and missing-data boundaries.",
  },
  {
    title: "Data provenance and freshness",
    description:
      "Source reliability, idempotent ingestion, duplicate detection, schema fingerprints, and stale/degraded warnings shown to staff.",
  },
  {
    title: "Alerts and human approvals",
    description:
      "Threshold alert rules, cooldowns, in-app notifications, and a second-admin plan review workflow that never executes a plan.",
  },
  {
    title: "Supabase authentication",
    description:
      "Signed ES256 JWT verification with JWKS rotation, expiry, issuer, audience, and claim validation.",
  },
  {
    title: "Role-aware workspace",
    description:
      "Exactly three roles, idempotent Citizen provisioning, and audited ADMIN-only role changes.",
  },
] as const;

const upcomingItems = [
  "Authoritative municipal outcome and asset datasets",
  "Licensed live source adapters and external notification delivery",
  "Department and administrative management",
  "Field-calibrated response outcome evaluation",
] as const;

const architectureCards = [
  {
    label: "Interface",
    title: "Next.js frontend",
    status: "Risk + operations",
    description:
      "Protected incident queue, MapLibre incident, H3 risk, and scenario-target maps, private evidence, intelligence suggestions, and a planning workspace.",
    tags: ["Next.js", "MapLibre", "H3", "TypeScript"],
  },
  {
    label: "Service",
    title: "FastAPI backend",
    status: "Governed operations APIs",
    description:
      "Verified JWTs, bounded H3 aggregation, versioned scoring, lifecycle transitions, signed Storage URLs, explainable intelligence, and bounded planning simulation.",
    tags: ["FastAPI", "H3", "PostGIS", "RBAC"],
  },
  {
    label: "Data",
    title: "PostgreSQL + PostGIS",
    status: "Alembic-managed schema",
    description:
      "Alembic-managed schema, PostGIS geography and GIST indexes, staff-only planning and governance tables, RLS policies, risk snapshots, and safe seed data.",
    tags: ["Supabase", "PostgreSQL", "PostGIS", "Alembic"],
  },
] as const;

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      fill="none"
      className="mt-0.5 size-4 shrink-0 text-emerald-400"
    >
      <path
        d="m3.5 8.5 3 3 6-7"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      fill="none"
      className="size-4 transition-transform group-hover:translate-x-0.5"
    >
      <path
        d="M3 8h10M9 4l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function HomePage() {
  return (
    <div id="top" className="relative min-h-dvh overflow-hidden">
      <div aria-hidden="true" className="site-grid" />
      <div aria-hidden="true" className="site-glow" />

      <SiteHeader />

      <main>
        <section className="mx-auto grid w-full max-w-7xl gap-10 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)] lg:items-start lg:gap-14 lg:pb-24 lg:pt-24">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-1.5 text-xs font-medium text-emerald-300">
              <span className="size-1.5 rounded-full bg-emerald-400" />
              {siteConfig.phase} · Urban response workspace
            </span>

            <h1 className="mt-6 max-w-4xl text-balance text-[2.65rem] font-semibold leading-[1.03] tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
              Urban response,{" "}
              <span className="bg-gradient-to-r from-emerald-300 via-teal-300 to-cyan-300 bg-clip-text text-transparent">
                connected by design.
              </span>
            </h1>

            <p className="mt-6 max-w-2xl text-pretty text-base leading-7 text-slate-400 sm:text-lg sm:leading-8">
              {siteConfig.description}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <a
                href="#status"
                className="group inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
              >
                Explore current status
                <ArrowIcon />
              </a>
              <a
                href="#architecture"
                className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10"
              >
                View architecture
              </a>
            </div>

            <dl className="mt-10 grid max-w-xl grid-cols-3 gap-4 border-t border-white/5 pt-6">
              <div>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-slate-600">
                  Phase
                </dt>
                <dd className="mt-1.5 text-sm font-medium text-slate-200">
                  {siteConfig.phase}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-slate-600">
                  API
                </dt>
                <dd className="mt-1.5 text-sm font-medium text-slate-200">
                  /api/v1
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-slate-600">
                  Stack
                </dt>
                <dd className="mt-1.5 text-sm font-medium text-slate-200">
                  Next.js + FastAPI
                </dd>
              </div>
            </dl>
          </div>

          <div className="lg:sticky lg:top-24">
            <BackendStatus />
            <p className="mt-3 px-1 text-xs leading-5 text-slate-600">
              This panel performs a real browser request to the API health
              endpoint. No status is pre-set or simulated.
            </p>
          </div>
        </section>

        <section
          id="status"
          aria-labelledby="status-heading"
          className="border-y border-white/5 bg-black/20"
        >
          <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:py-20">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-emerald-400/80">
                  Development status
                </p>
                <h2
                  id="status-heading"
                  className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl"
                >
                  What exists today
                </h2>
              </div>
              <p className="max-w-md text-sm leading-6 text-slate-500">
                Incident reporting, role-scoped queues, operational lifecycles,
                H3 risk analysis, planning simulations and governed research
                workflows are implemented. Risk outputs are research-oriented
                and require authoritative data to be meaningful.
              </p>
            </div>

            <div className="mt-10 grid gap-5 lg:grid-cols-2">
              <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.03] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-4">
                  <h3 className="text-base font-semibold text-white">
                    Incident operations implemented
                  </h3>
                  <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300">
                    Complete
                  </span>
                </div>
                <ul className="mt-5 space-y-4">
                  {foundationItems.map((item) => (
                    <li key={item.title} className="flex gap-3">
                      <CheckIcon />
                      <div>
                        <p className="text-sm font-medium text-slate-200">
                          {item.title}
                        </p>
                        <p className="mt-0.5 text-xs leading-5 text-slate-500">
                          {item.description}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-4">
                  <h3 className="text-base font-semibold text-white">
                    Needs real data or operator action
                  </h3>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-medium text-slate-400">
                    EXTERNAL
                  </span>
                </div>
                <ul className="mt-5 grid gap-3 sm:grid-cols-2">
                  {upcomingItems.map((item) => (
                    <li
                      key={item}
                      className="flex items-center gap-2.5 text-sm text-slate-500"
                    >
                      <span
                        aria-hidden="true"
                        className="size-1.5 shrink-0 rounded-full border border-slate-600"
                      />
                      {item}
                    </li>
                  ))}
                </ul>
                <p className="mt-6 rounded-lg border border-amber-400/10 bg-amber-400/[0.03] px-3.5 py-3 text-xs leading-5 text-amber-200/60">
                  These items depend on authoritative datasets, licensed
                  sources, or provider-side configuration. No finished module
                  is hidden from this list.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          id="architecture"
          aria-labelledby="architecture-heading"
          className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:py-20"
        >
          <div className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-emerald-400/80">
              Architecture
            </p>
            <h2
              id="architecture-heading"
              className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl"
            >
              A clean foundation for civic intelligence
            </h2>
            <p className="mt-4 text-sm leading-6 text-slate-500">
              Authentication, RBAC, RLS, spatial validation, evidence handling
              and incident foundations remain intact while risk and planning
              workflows operate as governed, research-oriented capabilities.
            </p>
          </div>

          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {architectureCards.map((card) => (
              <article
                key={card.title}
                className="group rounded-2xl border border-white/10 bg-white/[0.025] p-5 transition hover:border-white/20 hover:bg-white/[0.04] sm:p-6"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-600">
                    {card.label}
                  </span>
                  <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                    {card.status}
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-semibold tracking-tight text-white">
                  {card.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {card.description}
                </p>
                <ul className="mt-5 flex flex-wrap gap-1.5">
                  {card.tags.map((tag) => (
                    <li
                      key={tag}
                      className="rounded-md border border-white/5 bg-black/20 px-2 py-1 font-mono text-[10px] text-slate-500"
                    >
                      {tag}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          <div className="mt-10 flex flex-col gap-4 rounded-2xl border border-white/10 bg-gradient-to-r from-white/[0.04] to-transparent p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
            <div>
              <p className="text-sm font-medium text-slate-200">
                Urban risk intelligence runs alongside incident, spatial, and
                private-evidence operations. Outputs are research-oriented; no
                pilot is active.
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Health API:{" "}
                <code className="font-mono text-slate-400">
                  {getApiBaseUrl()}/api/v1/health
                </code>
              </p>
            </div>
            <a
              href={`${getApiBaseUrl()}/api/v1/health/database`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-emerald-300 transition hover:text-emerald-200"
            >
              Inspect database health
              <ArrowIcon />
            </a>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
