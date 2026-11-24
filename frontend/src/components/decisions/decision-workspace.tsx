"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { ScenarioMap } from "@/components/decisions/scenario-map";
import {
  compareDecisionStrategies,
  createDecisionAction,
  getDecisionScenario,
  listDecisionSimulations,
  listResponseResources,
  simulateDecisionScenario,
} from "@/lib/api/decisions";
import {
  listScenarioReviews,
  submitScenarioReview,
} from "@/lib/api/operations";
import {
  actionStatusTone,
  formatMinutes,
  formatMoney,
  formatPercent,
  hazardLabels,
  objectiveLabel,
  resourceStatusTone,
  scenarioStatusLabels,
  scenarioStatusTone,
  strategyLabels,
} from "@/lib/decisions";
import type {
  ComparisonResponse,
  DecisionAction,
  DecisionStrategy,
  ResponseActionType,
  ResponseResource,
  ScenarioDetail,
  SimulationListItem,
  SimulationResponse,
} from "@/types/decisions";
import type { ReviewRecord } from "@/types/operations";

const control =
  "w-full rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-emerald-400/50";

const ACTION_TYPES: ResponseActionType[] = [
  "INSPECT",
  "DISPATCH",
  "REPAIR",
  "CLEAN",
  "EVACUATE",
  "SHELTER",
  "MEDICAL",
  "UTILITY",
  "COMMUNICATION",
  "OTHER",
];

const STRATEGIES: DecisionStrategy[] = [
  "PRIORITY",
  "RISK_REDUCTION",
  "COST_EFFICIENT",
  "BALANCED",
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load the scenario.";
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/50 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-white">{value}</p>
      {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
    </div>
  );
}

function ActionRow({ action }: { action: DecisionAction }) {
  return (
    <li className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-100">{action.title}</p>
          <p className="mt-1 text-xs text-slate-500">
            {action.action_type} · priority {action.priority} ·{" "}
            {formatMinutes(action.duration_minutes)} ·{" "}
            {formatMoney(action.estimated_cost)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Target: {action.target_h3_cell_id ?? "none"} · expected reduction{" "}
            {action.expected_risk_reduction.toFixed(1)}
          </p>
        </div>
        <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-slate-400">
          {action.resource_requirements.length} resource requirement
          {action.resource_requirements.length === 1 ? "" : "s"}
        </span>
      </div>
    </li>
  );
}

export function DecisionWorkspace({ scenarioId }: { scenarioId: string }) {
  const { apiRequest } = useAuth();
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [resources, setResources] = useState<ResponseResource[]>([]);
  const [history, setHistory] = useState<SimulationListItem[]>([]);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [strategy, setStrategy] = useState<DecisionStrategy>("BALANCED");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("Clear blocked drain");
  const [actionType, setActionType] = useState<ResponseActionType>("CLEAN");
  const [priority, setPriority] = useState(4);
  const [duration, setDuration] = useState(60);
  const [reduction, setReduction] = useState(25);
  const [cost, setCost] = useState("100");
  const [targetCell, setTargetCell] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [quantity, setQuantity] = useState("1");

  const reload = useCallback(async () => {
    const [nextScenario, nextResources, nextHistory, nextReviews] =
      await Promise.all([
        getDecisionScenario(apiRequest, scenarioId),
        listResponseResources(apiRequest),
        listDecisionSimulations(apiRequest, scenarioId),
        listScenarioReviews(apiRequest, scenarioId),
      ]);
    setScenario(nextScenario);
    setResources(nextResources);
    setHistory(nextHistory);
    setReviews(nextReviews);
    setResourceId((current) => current || nextResources[0]?.id || "");
  }, [apiRequest, scenarioId]);

  useEffect(() => {
    let disposed = false;
    const timer = setTimeout(() => {
      void reload()
        .then(() => {
          if (!disposed) setError(null);
        })
        .catch((loadError) => {
          if (!disposed) setError(errorMessage(loadError));
        })
        .finally(() => {
          if (!disposed) setLoading(false);
        });
    }, 0);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [reload]);

  async function addAction() {
    if (!scenario) return;
    setBusy(true);
    setError(null);
    try {
      await createDecisionAction(apiRequest, scenario.id, {
        title,
        action_type: actionType,
        priority,
        duration_minutes: duration,
        expected_risk_reduction: reduction,
        estimated_cost: cost.trim() ? Number(cost) : null,
        target_h3_cell_id: targetCell.trim() || null,
        resource_requirements: resourceId
          ? [{ resource_id: resourceId, quantity_required: Number(quantity) }]
          : [],
      });
      await reload();
    } catch (createError) {
      setError(errorMessage(createError));
    } finally {
      setBusy(false);
    }
  }

  async function runSimulation() {
    if (!scenario) return;
    setBusy(true);
    setError(null);
    try {
      const result = await simulateDecisionScenario(
        apiRequest,
        scenario.id,
        strategy,
      );
      setSimulation(result);
      setHistory(await listDecisionSimulations(apiRequest, scenario.id));
    } catch (simulateError) {
      setError(errorMessage(simulateError));
    } finally {
      setBusy(false);
    }
  }

  async function runComparison() {
    if (!scenario) return;
    setBusy(true);
    setError(null);
    try {
      setComparison(
        await compareDecisionStrategies(apiRequest, scenario.id, STRATEGIES),
      );
    } catch (compareError) {
      setError(errorMessage(compareError));
    } finally {
      setBusy(false);
    }
  }

  async function submitForReview() {
    if (!simulation?.simulation_id) return;
    setBusy(true);
    setError(null);
    try {
      await submitScenarioReview(
        apiRequest,
        scenarioId,
        simulation.simulation_id,
        "Submitted from the decision workspace for human review.",
      );
      setReviews(await listScenarioReviews(apiRequest, scenarioId));
    } catch (reviewError) {
      setError(errorMessage(reviewError));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
        <p className="text-sm text-slate-400" role="status">
          Loading decision workspace…
        </p>
      </main>
    );
  }

  if (!scenario) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
        <p className="rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {error ?? "Scenario not found."}
        </p>
        <Link href="/decisions" className="mt-4 inline-block text-sm text-emerald-300">
          Back to decisions
        </Link>
      </main>
    );
  }

  const targetCells = Array.from(
    new Set(
      scenario.actions
        .map((action) => action.target_h3_cell_id)
        .filter((value): value is string => Boolean(value)),
    ),
  );

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/decisions" className="text-xs font-semibold text-emerald-300">
        ← Decision scenarios
      </Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Phase 6 decision workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            {scenario.name}
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            {hazardLabels[scenario.hazard_type]} ·{" "}
            {formatMinutes(scenario.horizon_minutes)} horizon ·{" "}
            {scenario.resolution} H3 resolution
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

      <div className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs leading-5 text-amber-100">
        Planning simulation only. Results are not approved orders. No dispatch,
        assignment, resource reservation, or incident mutation occurs.
      </div>
      {error ? (
        <p className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-white">Target cells</h2>
              <span className="text-xs text-slate-500">
                {targetCells.length} mapped
              </span>
            </div>
            <div className="mt-4">
              <ScenarioMap
                targetCells={targetCells}
                resolution={scenario.resolution}
              />
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="text-lg font-semibold text-white">Response actions</h2>
            {scenario.actions.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">
                No actions yet. Add the first planning action below.
              </p>
            ) : (
              <ul className="mt-3 space-y-2">
                {scenario.actions.map((action) => (
                  <ActionRow key={action.id} action={action} />
                ))}
              </ul>
            )}
            <div className="mt-6 border-t border-white/10 pt-5">
              <h3 className="text-sm font-semibold text-white">Add action</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <input
                  aria-label="Action title"
                  className={control}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
                <select
                  aria-label="Action type"
                  className={control}
                  value={actionType}
                  onChange={(event) =>
                    setActionType(event.target.value as ResponseActionType)
                  }
                >
                  {ACTION_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Priority"
                  type="number"
                  min={1}
                  max={5}
                  className={control}
                  value={priority}
                  onChange={(event) => setPriority(Number(event.target.value))}
                />
                <input
                  aria-label="Duration minutes"
                  type="number"
                  min={1}
                  className={control}
                  value={duration}
                  onChange={(event) => setDuration(Number(event.target.value))}
                />
                <input
                  aria-label="Expected reduction"
                  type="number"
                  min={0}
                  max={100}
                  className={control}
                  value={reduction}
                  onChange={(event) => setReduction(Number(event.target.value))}
                />
                <input
                  aria-label="Estimated cost"
                  type="number"
                  min={0}
                  className={control}
                  value={cost}
                  onChange={(event) => setCost(event.target.value)}
                />
                <input
                  aria-label="Target H3 cell"
                  className={`${control} sm:col-span-2`}
                  placeholder="Target H3 cell (optional)"
                  value={targetCell}
                  onChange={(event) => setTargetCell(event.target.value)}
                />
                <select
                  aria-label="Required resource"
                  className={control}
                  value={resourceId}
                  onChange={(event) => setResourceId(event.target.value)}
                >
                  <option value="">No resource requirement</option>
                  {resources.map((resource) => (
                    <option key={resource.id} value={resource.id}>
                      {resource.name} ({resource.availability_status})
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Quantity required"
                  type="number"
                  min={0.1}
                  step={0.1}
                  className={control}
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                />
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => void addAction()}
                className="mt-3 rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Add action
              </button>
            </div>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-semibold text-white">Run simulation</h2>
            <select
              aria-label="Strategy"
              className={`${control} mt-3`}
              value={strategy}
              onChange={(event) =>
                setStrategy(event.target.value as DecisionStrategy)
              }
            >
              {STRATEGIES.map((value) => (
                <option key={value} value={value}>
                  {strategyLabels[value]}
                </option>
              ))}
            </select>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void runSimulation()}
                className="rounded-lg bg-emerald-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Simulate
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void runComparison()}
                className="rounded-lg border border-white/15 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                Compare
              </button>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Solver is time-bounded. UNKNOWN resources block dependent actions.
            </p>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-semibold text-white">Planning resources</h2>
            <ul className="mt-3 space-y-2">
              {resources.length === 0 ? (
                <li className="text-xs text-slate-400">
                  No inventory records. Actions with no requirements remain
                  schedulable; resource availability is never invented.
                </li>
              ) : (
                resources.map((resource) => (
                  <li
                    key={resource.id}
                    className="rounded-xl border border-white/5 bg-slate-950/40 p-3 text-xs"
                  >
                    <div className="flex justify-between gap-2">
                      <span className="font-medium text-slate-200">
                        {resource.name}
                      </span>
                      <span className="text-slate-500">
                        {resource.quantity_available} {resource.unit}
                      </span>
                    </div>
                    <span
                      className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-[10px] ${resourceStatusTone(
                        resource.availability_status,
                      )}`}
                    >
                      {resource.availability_status}
                    </span>
                    {resource.availability_source ? (
                      <p className="mt-1 text-[11px] text-slate-500">
                        Source: {resource.availability_source}
                      </p>
                    ) : null}
                  </li>
                ))
              )}
            </ul>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-semibold text-white">Simulation history</h2>
            <ul className="mt-3 space-y-2 text-xs">
              {history.length === 0 ? (
                <li className="text-slate-400">No persisted simulations yet.</li>
              ) : (
                history.slice(0, 5).map((item) => (
                  <li key={item.id} className="rounded-lg bg-slate-950/40 p-2">
                    <span className="text-slate-200">{strategyLabels[item.strategy]}</span>
                    <span className="ml-2 text-slate-500">{item.status}</span>
                    <span className="ml-2 text-slate-500">{item.duration_ms} ms</span>
                  </li>
                ))
              )}
            </ul>
          </section>
        </aside>
      </div>

      {simulation ? (
        <section className="mt-6 rounded-2xl border border-emerald-300/20 bg-emerald-300/5 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">
                {strategyLabels[simulation.strategy]} simulation
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                {simulation.status} · {simulation.model_version} ·{" "}
                {simulation.plan.solver.algorithm as string}
              </p>
            </div>
            <span className="rounded-full border border-emerald-300/25 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
              Planning only
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Metric
              label="Scheduled"
              value={`${simulation.plan.metrics.scheduled_actions}/${simulation.plan.metrics.total_actions}`}
              detail={`${formatPercent(simulation.plan.metrics.action_coverage)} coverage`}
            />
            <Metric
              label="Risk reduction"
              value={simulation.plan.metrics.planned_reduction.toFixed(1)}
              detail={`${formatPercent(simulation.plan.metrics.reduction_rate)} of planned`}
            />
            <Metric
              label="Known cost"
              value={formatMoney(simulation.plan.metrics.total_known_cost)}
              detail={
                simulation.plan.metrics.budget_limit !== null
                  ? `Budget ${formatMoney(simulation.plan.metrics.budget_limit)}`
                  : "No budget limit"
              }
            />
            <Metric
              label="Makespan"
              value={formatMinutes(simulation.plan.metrics.makespan_minutes)}
              detail={`Horizon ${formatMinutes(simulation.plan.metrics.horizon_minutes)}`}
            />
            <Metric
              label="Coverage"
              value={formatPercent(simulation.plan.metrics.priority_coverage)}
              detail="Priority-weighted"
            />
            <Metric
              label="Objective"
              value={simulation.plan.objective_score.toFixed(3)}
              detail="Planning heuristic"
            />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-white">Action plan</h3>
              <ul className="mt-2 space-y-2">
                {simulation.plan.actions.map((action) => (
                  <li
                    key={action.action_id}
                    className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-slate-100">{action.title}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] ${actionStatusTone(
                          action.status,
                        )}`}
                      >
                        {action.status}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-500">
                      {action.start_minute === null
                        ? "Not scheduled"
                        : `${formatMinutes(action.start_minute)} → ${formatMinutes(action.end_minute)}`}{" "}
                      · reduction {action.planned_reduction.toFixed(1)}
                    </p>
                    {action.reasons.length > 0 ? (
                      <p className="mt-1 text-amber-200/80">{action.reasons.join(", ")}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Assumptions and limits</h3>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-400">
                {simulation.assumptions.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
                {simulation.warnings.map((item) => (
                  <li key={item} className="text-amber-200/80">
                    • {item}
                  </li>
                ))}
                {simulation.limitations.map((item) => (
                  <li key={item} className="text-slate-500">
                    • {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      {simulation?.simulation_id ? (
        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Plan review</h2>
              <p className="mt-1 text-xs text-slate-400">
                A human approval records a planning decision only. It does not
                authorize dispatch or execution.
              </p>
            </div>
            {reviews.some((review) =>
              ["SUBMITTED", "APPROVED", "REVISION_REQUESTED"].includes(
                review.status,
              ),
            ) ? null : (
              <button
                type="button"
                disabled={busy}
                onClick={() => void submitForReview()}
                className="rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
              >
                Submit for review
              </button>
            )}
          </div>
          {reviews.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No review submitted.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {reviews.map((review) => (
                <li
                  key={review.id}
                  className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-400"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-medium text-slate-100">
                      {review.title}
                    </span>
                    <span className="rounded-full border border-white/10 px-2 py-1 text-[10px]">
                      {review.status}
                    </span>
                  </div>
                  <p className="mt-1">
                    Submitted by {review.submitted_by_name ?? "unknown"}
                    {review.reviewed_by_name
                      ? ` · reviewed by ${review.reviewed_by_name}`
                      : ""}
                  </p>
                  {review.decision_note ? (
                    <p className="mt-1 text-slate-500">{review.decision_note}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {comparison ? (
        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-lg font-semibold text-white">Strategy comparison</h2>
          <p className="mt-1 text-xs text-slate-400">
            Winner: {comparison.comparison.winner ?? "none"} · same inputs and
            solver limits.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {comparison.comparison.results.map((plan) => (
              <div key={plan.strategy} className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs">
                <div className="flex justify-between gap-2">
                  <span className="font-medium text-slate-100">
                    #{plan.rank} {strategyLabels[plan.strategy]}
                  </span>
                  <span className="text-emerald-200">{plan.objective_score.toFixed(3)}</span>
                </div>
                <p className="mt-1 text-slate-500">
                  {plan.metrics.scheduled_actions} scheduled ·{" "}
                  {plan.metrics.planned_reduction.toFixed(1)} reduction ·{" "}
                  {formatMoney(plan.metrics.total_known_cost)}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(plan.objective_components).map(([key, value]) => (
                    <span key={key} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400">
                      {objectiveLabel(key)} {formatPercent(value)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
