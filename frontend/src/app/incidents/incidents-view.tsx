"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { IncidentCard } from "@/components/incidents/incident-card";
import { listIncidents } from "@/lib/api/incidents";
import {
  categories,
  categoryLabels,
  severities,
  severityLabels,
  statuses,
  statusLabels,
} from "@/lib/incidents";
import type {
  IncidentCategory,
  IncidentList,
  IncidentSeverity,
  IncidentStatus,
} from "@/types/incidents";

const selectClass =
  "rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-emerald-400/50";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load incidents.";
}

export function IncidentsView() {
  const { profile, apiRequest } = useAuth();
  const [data, setData] = useState<IncidentList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [category, setCategory] = useState<IncidentCategory | "">("");
  const [severity, setSeverity] = useState<IncidentSeverity | "">("");
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listIncidents(apiRequest, {
        page,
        pageSize: 12,
        status,
        category,
        severity,
        query,
      });
      setData(next);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [apiRequest, category, page, query, severity, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 200);
    return () => window.clearTimeout(timer);
  }, [load]);

  const isStaff = profile?.role === "WORKER" || profile?.role === "ADMIN";

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Incident operations
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            {isStaff ? "Citywide incident queue" : "Your reports"}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            {isStaff
              ? "Review, assign, and move incidents through the response lifecycle."
              : "Track the reports you submitted and their current response status."}
          </p>
        </div>
        <Link
          href="/incidents/new"
          className="rounded-xl bg-emerald-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
        >
          Report an incident
        </Link>
      </div>

      <section className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Search title, description, address"
            aria-label="Search incidents"
            className={`${selectClass} w-full`}
          />
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as IncidentStatus | "");
              setPage(1);
            }}
            aria-label="Filter by status"
            className={selectClass}
          >
            <option value="">All statuses</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {statusLabels[value]}
              </option>
            ))}
          </select>
          <select
            value={category}
            onChange={(event) => {
              setCategory(event.target.value as IncidentCategory | "");
              setPage(1);
            }}
            aria-label="Filter by category"
            className={selectClass}
          >
            <option value="">All categories</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabels[value]}
              </option>
            ))}
          </select>
          <select
            value={severity}
            onChange={(event) => {
              setSeverity(event.target.value as IncidentSeverity | "");
              setPage(1);
            }}
            aria-label="Filter by severity"
            className={selectClass}
          >
            <option value="">All severities</option>
            {severities.map((value) => (
              <option key={value} value={value}>
                {severityLabels[value]}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="mt-6 flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500" role="status">
          {loading
            ? "Loading incidents…"
            : `${data?.total ?? 0} incident${data?.total === 1 ? "" : "s"}`}
        </p>
        {data && data.pages > 1 ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <button
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              className="rounded-lg border border-white/10 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              {data.page} / {data.pages}
            </span>
            <button
              type="button"
              disabled={page >= data.pages || loading}
              onClick={() => setPage((value) => value + 1)}
              className="rounded-lg border border-white/10 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mt-6 rounded-2xl border border-rose-300/20 bg-rose-300/5 p-6">
          <p className="text-sm text-rose-100">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-4 rounded-lg border border-white/15 px-4 py-2 text-sm text-white"
          >
            Retry
          </button>
        </div>
      ) : loading && !data ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-44 animate-pulse rounded-2xl border border-white/5 bg-white/[0.03]"
            />
          ))}
        </div>
      ) : data && data.items.length > 0 ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {data.items.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-white/15 p-10 text-center">
          <h2 className="text-lg font-semibold text-white">No incidents found</h2>
          <p className="mt-2 text-sm text-slate-400">
            {isStaff
              ? "No reports match these filters yet."
              : "You have not submitted a report that matches these filters."}
          </p>
          <Link
            href="/incidents/new"
            className="mt-5 inline-flex rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950"
          >
            Report an incident
          </Link>
        </div>
      )}
    </main>
  );
}
