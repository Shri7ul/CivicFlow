"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { listIncidents } from "@/lib/api/incidents";
import { navigationForRole, roleLabel } from "@/lib/auth/routing";
import type { Incident, IncidentStatus } from "@/types/incidents";

const STATUSES: readonly IncidentStatus[] = [
  "OPEN",
  "VERIFIED",
  "ASSIGNED",
  "ACCEPTED",
  "ACKNOWLEDGED",
  "IN_PROGRESS",
  "COMPLETION_SUBMITTED",
  "VERIFIED_COMPLETED",
  "RESOLVED",
  "CLOSED",
];

const statusLabels: Record<IncidentStatus, string> = {
  OPEN: "Open",
  VERIFIED: "Verified",
  ASSIGNED: "Assigned",
  ACCEPTED: "Accepted",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  COMPLETION_SUBMITTED: "Completion submitted",
  VERIFIED_COMPLETED: "Verified completed",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
};

const quickActions = [
  { path: "/incidents", label: "View incidents" },
  { path: "/incidents/new", label: "Report incident" },
  { path: "/map", label: "Incident map" },
  { path: "/risk", label: "Risk map" },
  { path: "/decisions", label: "Scenario planning" },
  { path: "/operations", label: "Operations" },
  { path: "/validation", label: "Validation" },
  { path: "/pilot", label: "Pilot controls" },
] as const;

type DashboardData = {
  totals: Record<IncidentStatus, number>;
  recent: Incident[];
  total: number;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load dashboard data.";
}

export function DashboardView() {
  const { profile, apiRequest } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const role = profile?.role ?? "CITIZEN";

  useEffect(() => {
    if (!profile) return;
    const controller = new AbortController();
    let active = true;

    void (async () => {
      try {
        // Counts come from the same visibility-scoped endpoint the queue uses:
        // citizens see their own reports, staff see the citywide queue.
        const [countResults, recent] = await Promise.all([
          Promise.all(
            STATUSES.map((status) =>
              listIncidents(
                apiRequest,
                { status, page: 1, pageSize: 1 },
                { signal: controller.signal },
              ),
            ),
          ),
          listIncidents(
            apiRequest,
            { page: 1, pageSize: 5 },
            { signal: controller.signal },
          ),
        ]);
        if (!active) return;
        const totals = {} as Record<IncidentStatus, number>;
        STATUSES.forEach((status, index) => {
          totals[status] = countResults[index]?.total ?? 0;
        });
        setData({
          totals,
          recent: recent.items,
          total: recent.total,
        });
      } catch (loadError) {
        if (controller.signal.aborted) return;
        setError(errorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [apiRequest, profile, reloadKey]);

  const retry = useCallback(() => {
    setLoading(true);
    setError(null);
    setReloadKey((value) => value + 1);
  }, []);
  const allowedPaths = useMemo(() => navigationForRole(role), [role]);
  const actions = quickActions.filter((action) =>
    allowedPaths.some(
      (path) => action.path === path || action.path.startsWith(`${path}/`),
    ),
  );

  if (!profile) {
    return null;
  }

  const attention = data
    ? data.totals.OPEN + data.totals.ACKNOWLEDGED + data.totals.IN_PROGRESS
    : null;

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Workspace overview
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Welcome, {profile.full_name}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            {role === "CITIZEN"
              ? "Track your reports and their response status. Counts below cover only the incidents you reported."
              : "Monitor the shared incident queue and move reports through the response lifecycle. Counts are scoped to your role."}
          </p>
        </div>
        <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-xs font-semibold text-emerald-200">
          {roleLabel(profile.role)}
        </span>
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/5 px-5 py-4"
        >
          <p className="text-sm text-rose-100">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="rounded-lg border border-rose-200/30 px-3 py-1.5 text-xs font-medium text-rose-100 transition hover:bg-rose-200/10"
          >
            Retry
          </button>
        </div>
      ) : null}

      <section aria-label="Incident summary" className="mt-8">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" role="status">
            {STATUSES.slice(0, 4).map((status) => (
              <div
                key={status}
                className="h-24 animate-pulse rounded-2xl border border-white/5 bg-white/[0.03]"
              />
            ))}
          </div>
        ) : data ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {STATUSES.slice(0, 4).map((status) => (
                <div
                  key={status}
                  className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {statusLabels[status]}
                  </p>
                  <p className="mt-2 text-3xl font-semibold tracking-tight text-white">
                    {data.totals[status]}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              {data.total === 0
                ? "No incidents have been reported in this scope yet."
                : `${data.total} incident${data.total === 1 ? "" : "s"} in this scope · ${attention} awaiting action.`}
            </p>
          </>
        ) : null}
      </section>

      <div className="mt-8 grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">Recent incidents</h2>
            <Link
              href="/incidents"
              className="text-xs font-medium text-emerald-300 underline-offset-4 hover:underline"
            >
              Open full queue
            </Link>
          </div>
          {loading ? (
            <p role="status" className="mt-5 text-sm text-slate-400">
              Loading incidents…
            </p>
          ) : data && data.recent.length > 0 ? (
            <ul className="mt-5 divide-y divide-white/5">
              {data.recent.map((incident) => (
                <li key={incident.id} className="py-3 first:pt-0">
                  <Link
                    href={`/incidents/${incident.id}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg text-sm transition hover:text-emerald-200"
                  >
                    <span className="font-medium text-slate-200">
                      {incident.title}
                    </span>
                    <span className="rounded-full border border-white/10 bg-slate-950/60 px-2.5 py-1 text-[11px] text-slate-400">
                      {statusLabels[incident.status]}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 rounded-2xl border border-white/5 bg-slate-950/40 p-5 text-sm text-slate-400">
              No incidents in this scope yet. Reports you submit will appear here
              with their current status.
            </p>
          )}
        </section>

        <aside className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
          <h2 className="text-lg font-semibold text-white">Quick actions</h2>
          <div className="mt-5 flex flex-wrap gap-2">
            {actions.map((action) => (
              <Link
                key={action.path}
                href={action.path}
                className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/30 hover:bg-white/5"
              >
                {action.label}
              </Link>
            ))}
          </div>
          <dl className="mt-8 space-y-4 border-t border-white/5 pt-6 text-sm">
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
                Account status
              </dt>
              <dd className="mt-1 text-slate-300">
                {profile.is_active ? "Active" : "Inactive"}
              </dd>
            </div>
          </dl>
        </aside>
      </div>
    </main>
  );
}
