"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  createDecisionScenario,
  createResponseResource,
  listDecisionScenarios,
  listResponseResources,
} from "@/lib/api/decisions";
import {
  hazardLabels,
  resourceStatusLabels,
  scenarioStatusLabels,
  scenarioStatusTone,
} from "@/lib/decisions";
import type {
  ResponseResource,
  ScenarioHazard,
  ScenarioSummary,
} from "@/types/decisions";

const control =
  "w-full rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-emerald-400/50";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load decisions.";
}

export function DecisionDashboard() {
  const { apiRequest } = useAuth();
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [resources, setResources] = useState<ResponseResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("Monsoon drain failure");
  const [hazard, setHazard] = useState<ScenarioHazard>("FLOOD");
  const [horizon, setHorizon] = useState(240);
  const [budget, setBudget] = useState("500");
  const [resourceName, setResourceName] = useState("Drain crew");
  const [resourceUnit, setResourceUnit] = useState("crew");
  const [resourceQuantity, setResourceQuantity] = useState("2");
  const [resourceStatus, setResourceStatus] =
    useState<ResponseResource["availability_status"]>("PLANNING_ASSUMPTION");
  const [resourceSource, setResourceSource] = useState("Planning assumption");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    void Promise.all([
      listDecisionScenarios(apiRequest),
      listResponseResources(apiRequest),
    ])
      .then(([nextScenarios, nextResources]) => {
        if (disposed) return;
        setScenarios(nextScenarios);
        setResources(nextResources);
        setError(null);
      })
      .catch((loadError) => {
        if (!disposed) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [apiRequest]);

  async function createScenario() {
    setBusy(true);
    setFormError(null);
    try {
      const created = await createDecisionScenario(apiRequest, {
        name,
        hazard_type: hazard,
        horizon_minutes: horizon,
        budget_limit: budget.trim() ? Number(budget) : null,
      });
      setScenarios((current) => [created, ...current]);
    } catch (createError) {
      setFormError(errorMessage(createError));
    } finally {
      setBusy(false);
    }
  }

  async function createResource() {
    setBusy(true);
    setFormError(null);
    try {
      const created = await createResponseResource(apiRequest, {
        name: resourceName,
        resource_type: "PERSONNEL",
        unit: resourceUnit,
        quantity_available: Number(resourceQuantity),
        availability_status: resourceStatus,
        availability_source: resourceSource.trim() || null,
        available_as_of: new Date().toISOString(),
      });
      setResources((current) => [created, ...current]);
    } catch (createError) {
      setFormError(errorMessage(createError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Phase 6 decision intelligence
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Scenario planning workspace
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Compare response strategies against explicit planning assumptions.
            Simulations schedule work only; they never dispatch units, reserve
            resources, or mutate incidents.
          </p>
        </div>
        <span className="rounded-full border border-amber-300/25 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-100">
          Staff planning only
        </span>
      </div>

      {error ? (
        <p className="mt-6 rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {error}
        </p>
      ) : null}
      {formError ? (
        <p className="mt-6 rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {formError}
        </p>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.45fr_0.75fr]">
        <section>
          <h2 className="text-lg font-semibold text-white">Scenarios</h2>
          {loading ? (
            <p className="mt-4 text-sm text-slate-400" role="status">
              Loading scenarios…
            </p>
          ) : scenarios.length === 0 ? (
            <p className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-400">
              No decision scenarios yet. Create one to begin planning.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {scenarios.map((scenario) => (
                <li key={scenario.id}>
                  <Link
                    href={`/decisions/${scenario.id}`}
                    className="block rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-300/30 hover:bg-emerald-300/5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-medium text-white">{scenario.name}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {hazardLabels[scenario.hazard_type]} ·{" "}
                          {scenario.action_count} actions ·{" "}
                          {scenario.simulation_count} simulations
                        </p>
                      </div>
                      <span
                        className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-wide ${scenarioStatusTone(
                          scenario.status,
                        )}`}
                      >
                        {scenarioStatusLabels[scenario.status]}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="space-y-5">
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-semibold text-white">New scenario</h2>
            <div className="mt-4 space-y-3">
              <input
                aria-label="Scenario name"
                className={control}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <select
                aria-label="Hazard"
                className={control}
                value={hazard}
                onChange={(event) =>
                  setHazard(event.target.value as ScenarioHazard)
                }
              >
                {Object.entries(hazardLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <input
                aria-label="Horizon minutes"
                type="number"
                min={60}
                max={10080}
                className={control}
                value={horizon}
                onChange={(event) => setHorizon(Number(event.target.value))}
              />
              <input
                aria-label="Budget limit"
                type="number"
                min={0}
                className={control}
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void createScenario()}
                className="w-full rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
              >
                Create scenario
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-semibold text-white">Planning resources</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Availability is explicit. UNKNOWN stays unknown and blocks actions
              that require it.
            </p>
            <div className="mt-4 space-y-3">
              <input
                className={control}
                aria-label="Resource name"
                value={resourceName}
                onChange={(event) => setResourceName(event.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  className={control}
                  aria-label="Resource unit"
                  value={resourceUnit}
                  onChange={(event) => setResourceUnit(event.target.value)}
                />
                <input
                  aria-label="Resource quantity"
                  type="number"
                  min={0}
                  className={control}
                  value={resourceQuantity}
                  onChange={(event) => setResourceQuantity(event.target.value)}
                />
              </div>
              <select
                aria-label="Resource availability"
                className={control}
                value={resourceStatus}
                onChange={(event) =>
                  setResourceStatus(
                    event.target.value as ResponseResource["availability_status"],
                  )
                }
              >
                {Object.entries(resourceStatusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <input
                className={control}
                aria-label="Availability source"
                placeholder="Source / planning assumption"
                value={resourceSource}
                onChange={(event) => setResourceSource(event.target.value)}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void createResource()}
                className="w-full rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:border-white/25 disabled:opacity-50"
              >
                Add resource record
              </button>
            </div>
            <ul className="mt-4 space-y-2 text-xs text-slate-400">
              {resources.slice(0, 6).map((resource) => (
                <li key={resource.id} className="flex justify-between gap-2">
                  <span className="truncate">{resource.name}</span>
                  <span className="shrink-0 text-slate-500">
                    {resource.quantity_available} {resource.unit} ·{" "}
                    {resource.availability_status}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </main>
  );
}
