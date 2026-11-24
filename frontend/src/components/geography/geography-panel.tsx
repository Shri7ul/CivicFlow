"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  getDhakaReadiness,
  getGeographicContexts,
  getPilotAreaCandidates,
  getScopedWorkspace,
} from "@/lib/api/geo";
import { DEFAULT_GEOGRAPHIC_CONTEXT } from "@/config/geography";
import type {
  DhakaReadinessReport,
  GeographicContext,
  PilotAreaSelection,
} from "@/types/geography";

export interface GeographyPanelViewProps {
  contexts: GeographicContext[];
  selectedContext: string;
  readiness: DhakaReadinessReport | null;
  pilotAreas: PilotAreaSelection | null;
  workspace: Record<string, unknown> | null;
  error: string | null;
  onSelect?: (key: string) => void;
}

function contextList(workspace: Record<string, unknown> | null): number {
  const rows = workspace?.snapshots;
  return Array.isArray(rows) ? rows.length : 0;
}

/** Pure presentation component; all displayed values come from the API. */
export function GeographyPanelView({
  contexts,
  selectedContext,
  readiness,
  pilotAreas,
  workspace,
  error,
  onSelect,
}: GeographyPanelViewProps) {
  const active = contexts.find((item) => item.key === selectedContext);
  return (
    <section
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
      data-testid="geography-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">
            Geographic context
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Research identity, not operational status. NYC data is never Dhaka
            operational evidence.
          </p>
        </div>
        <label className="text-sm text-slate-300">
          Context
          <select
            aria-label="Geographic context"
            className="ml-2 rounded-md border border-slate-700 bg-slate-950 px-2 py-1"
            value={selectedContext}
            onChange={(event) => onSelect?.(event.target.value)}
          >
            {contexts.map((item) => (
              <option key={item.key} value={item.key}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <p className="mt-4 text-sm text-rose-300" role="alert">
          {error}
        </p>
      ) : null}

      {active ? (
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">Boundary status</dt>
            <dd className="text-slate-200">{active.boundary_status}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Pilot eligible</dt>
            <dd className="text-slate-200">
              {active.is_pilot_eligible ? "YES" : "NO"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-slate-500">Boundary basis</dt>
            <dd className="text-slate-200">{active.boundary_basis}</dd>
          </div>
        </dl>
      ) : null}

      <div className="mt-4 rounded-lg border border-amber-800/60 bg-amber-950/30 p-3 text-sm text-amber-200">
        Phase 12 preparations only: no pilot is approved, no model is activated,
        no field observation is claimed and no automated action is enabled.
      </div>

      {readiness ? (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-slate-200">
            Dhaka readiness ({readiness.overall})
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            Activation authorized:{" "}
            {readiness.pilot_activation_authorized ? "YES" : "NO"}
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {readiness.categories.map((category) => (
              <li
                key={category.key}
                className="flex justify-between gap-3 border-b border-slate-800 py-1"
              >
                <span className="text-slate-300">{category.label}</span>
                <span className="font-mono text-xs text-slate-400">
                  {category.status}
                  {category.mandatory ? "" : " (advisory)"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {pilotAreas ? (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-slate-200">
            Pilot area selection: {pilotAreas.status}
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            {pilotAreas.selected_area ?? "No area selected"}
          </p>
          <ul className="mt-2 space-y-1 text-xs text-slate-400">
            {pilotAreas.candidates.map((candidate) => (
              <li key={candidate.name}>
                {candidate.name} — {candidate.status}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {workspace ? (
        <p className="mt-5 text-xs text-slate-400" data-testid="scoped-count">
          Server-scoped evidence rows for {selectedContext}:{" "}
          {contextList(workspace)}
        </p>
      ) : null}
    </section>
  );
}

export function GeographyPanel() {
  const { apiRequest } = useAuth();
  const [contexts, setContexts] = useState<GeographicContext[]>([]);
  const [selectedContext, setSelectedContext] = useState<string>(
    DEFAULT_GEOGRAPHIC_CONTEXT,
  );
  const [readiness, setReadiness] = useState<DhakaReadinessReport | null>(null);
  const [pilotAreas, setPilotAreas] = useState<PilotAreaSelection | null>(null);
  const [workspace, setWorkspace] = useState<Record<string, unknown> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getGeographicContexts(apiRequest, { signal: controller.signal }),
      getDhakaReadiness(apiRequest, { signal: controller.signal }),
      getPilotAreaCandidates(apiRequest, { signal: controller.signal }),
    ])
      .then(([contextResponse, readinessResponse, pilotResponse]) => {
        setContexts(contextResponse.items);
        setReadiness(readinessResponse);
        setPilotAreas(pilotResponse);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Load failed");
        }
      });
    return () => controller.abort();
  }, [apiRequest]);

  useEffect(() => {
    const controller = new AbortController();
    getScopedWorkspace(apiRequest, selectedContext, {
      signal: controller.signal,
    })
      .then((response) => setWorkspace(response))
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Load failed");
        }
      });
    return () => controller.abort();
  }, [apiRequest, selectedContext]);

  const handleSelect = useCallback((key: string) => {
    setSelectedContext(key);
    setWorkspace(null);
  }, []);

  return (
    <GeographyPanelView
      contexts={contexts}
      selectedContext={selectedContext}
      readiness={readiness}
      pilotAreas={pilotAreas}
      workspace={workspace}
      error={error}
      onSelect={handleSelect}
    />
  );
}
