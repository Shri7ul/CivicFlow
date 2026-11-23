"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { roleLabel } from "@/lib/auth/routing";

const roleCapabilities: Record<string, readonly string[]> = {
  CITIZEN: [
    "Report civic incidents with a precise location",
    "Track your reports and their response status",
    "Edit an open report before staff acknowledge it",
  ],
  WORKER: [
    "Review the citywide incident queue",
    "Assign reports to municipal departments",
    "Advance incidents through the response lifecycle",
    "Review duplicate and related-incident suggestions",
    "Inspect H3 risk cells, trends, and infrastructure exposure",
    "Plan response scenarios with explicit resource assumptions",
  ],
  ADMIN: [
    "Oversee the citywide incident queue",
    "Use the same audited response workflow as workers",
    "Review explainable intelligence suggestions and relationships",
    "Inspect urban risk cells and model limitations",
    "Plan and compare response scenarios without dispatching resources",
    "Manage application roles and privileged access",
  ],
};

export function DashboardView() {
  const { profile } = useAuth();

  if (!profile) {
    return null;
  }

  const capabilities = roleCapabilities[profile.role] ?? [];

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Phase 6 decision intelligence
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Welcome, {profile.full_name}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            This is the protected CivicFlow workspace. Report civic incidents,
            follow their lifecycle, and coordinate the municipal response from a
            single auditable queue.
          </p>
        </div>
        <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-xs font-semibold text-emerald-200">
          {roleLabel(profile.role)}
        </span>
      </div>

      <div className="mt-10 grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">
              Your role capabilities
            </h2>
            <span className="rounded-lg bg-slate-950/60 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {profile.role}
            </span>
          </div>
          <ul className="mt-5 grid gap-3 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <li
                key={capability}
                className="rounded-2xl border border-white/5 bg-slate-950/40 p-4 text-sm leading-6 text-slate-300"
              >
                <span className="mr-2 text-emerald-400" aria-hidden="true">
                  •
                </span>
                {capability}
              </li>
            ))}
          </ul>
          <p className="mt-6 text-xs leading-5 text-slate-500">
            Backend endpoints enforce this role. The frontend never grants access
            on its own, and role values from the browser are ignored.
          </p>
        </section>

        <aside className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
          <h2 className="text-lg font-semibold text-white">Account</h2>
          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Profile ID
              </dt>
              <dd className="mt-1 break-all font-mono text-xs text-slate-300">
                {profile.id}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Status
              </dt>
              <dd className="mt-1 text-slate-300">
                {profile.is_active ? "Active" : "Inactive"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Phone
              </dt>
              <dd className="mt-1 text-slate-300">
                {profile.phone ?? "Not provided"}
              </dd>
            </div>
          </dl>
          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              href="/incidents"
              className="inline-flex rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
            >
              View incidents
            </Link>
            <Link
              href="/incidents/new"
              className="inline-flex rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:border-white/25"
            >
              Report an incident
            </Link>
            <Link
              href="/map"
              className="inline-flex rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:border-white/25"
            >
              Open incident map
            </Link>
            <Link
              href="/risk"
              className="inline-flex rounded-lg border border-amber-300/25 bg-amber-300/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-300/15"
            >
              Open risk map
            </Link>
            <Link
              href="/decisions"
              className="inline-flex rounded-lg border border-sky-300/25 bg-sky-300/10 px-4 py-2 text-sm font-medium text-sky-100 transition hover:bg-sky-300/15"
            >
              Plan scenarios
            </Link>
          </div>
        </aside>
      </div>
    </main>
  );
}
