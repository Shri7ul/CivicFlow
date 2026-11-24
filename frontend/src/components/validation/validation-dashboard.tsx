"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Phase9Research } from "@/components/validation/phase9-research";
import {
  getPhase9Report,
  getPhase9Research,
  getValidationExperiment,
  getValidationOverview,
  getValidationReport,
  runCorrelationValidation,
  runDecisionValidation,
  runRiskValidation,
} from "@/lib/api/validation";
import type {
  Phase9Report,
  Phase9Summary,
  ValidationDataset,
  ValidationEvidenceKind,
  ValidationExperiment,
  ValidationExperimentDetail,
  ValidationOverview,
} from "@/types/validation";

type JsonRecord = Record<string, unknown>;

const control =
  "rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 disabled:opacity-50";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load validation results.";
}

function asRecord(value: unknown): JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function numberValue(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(3)
    : "—";
}

function evidenceLabel(kind: ValidationEvidenceKind): string {
  if (kind === "EMPIRICAL_OBSERVATIONAL") return "Empirical observational";
  if (kind === "SYNTHETIC_FIXTURE") return "Synthetic fixture";
  return "Simulated planning";
}

function evidenceTone(kind: ValidationEvidenceKind): string {
  if (kind === "EMPIRICAL_OBSERVATIONAL") {
    return "border-sky-300/25 bg-sky-300/10 text-sky-200";
  }
  if (kind === "SYNTHETIC_FIXTURE") {
    return "border-amber-300/25 bg-amber-300/10 text-amber-200";
  }
  return "border-violet-300/25 bg-violet-300/10 text-violet-200";
}

function statusTone(status: string): string {
  if (status === "COMPLETED") {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  if (status === "RUNNING" || status === "INSUFFICIENT_DATA") {
    return "border-amber-300/25 bg-amber-300/10 text-amber-200";
  }
  return "border-rose-300/25 bg-rose-300/10 text-rose-200";
}

function Card({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "default" | "warn" | "good";
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          tone === "warn"
            ? "text-amber-200"
            : tone === "good"
              ? "text-emerald-200"
              : "text-white"
        }`}
      >
        {value}
      </p>
      {detail ? <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p> : null}
    </div>
  );
}

function MethodTable({ metrics }: { metrics: JsonRecord }) {
  const rows = Object.entries(asRecord(metrics.methods))
    .map(([name, raw]) => ({ name, values: asRecord(raw) }))
    .filter((row) => Object.keys(row.values).length > 0);
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No completed ranking metrics.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
          <tr>
            <th className="pb-2 pr-4 font-semibold">Method</th>
            <th className="pb-2 pr-4 font-semibold">PR-AUC</th>
            <th className="pb-2 pr-4 font-semibold">ROC-AUC</th>
            <th className="pb-2 pr-4 font-semibold">Precision@k</th>
            <th className="pb-2 pr-4 font-semibold">Recall@k</th>
            <th className="pb-2 font-semibold">Folds</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-300">
          {rows.map((row) => (
            <tr key={row.name}>
              <td className="py-2 pr-4 font-medium text-slate-200">
                {row.name.replaceAll("_", " ")}
              </td>
              <td className="py-2 pr-4">{numberValue(row.values.pr_auc)}</td>
              <td className="py-2 pr-4">{numberValue(row.values.roc_auc)}</td>
              <td className="py-2 pr-4">
                {numberValue(row.values.precision_at_k)}
              </td>
              <td className="py-2 pr-4">{numberValue(row.values.recall_at_k)}</td>
              <td className="py-2">
                {numberValue(row.values.completed_folds)} /{" "}
                {numberValue(row.values.fold_count)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExperimentRows({
  experiments,
  onReport,
  busyId,
}: {
  experiments: ValidationExperiment[];
  onReport: (experiment: ValidationExperiment) => Promise<void>;
  busyId: string | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
          <tr>
            <th className="pb-2 pr-4 font-semibold">Experiment</th>
            <th className="pb-2 pr-4 font-semibold">Evidence</th>
            <th className="pb-2 pr-4 font-semibold">Status</th>
            <th className="pb-2 pr-4 font-semibold">Records</th>
            <th className="pb-2 pr-4 font-semibold">Completed</th>
            <th className="pb-2 font-semibold">Report</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-300">
          {experiments.map((experiment) => (
            <tr key={experiment.id}>
              <td className="py-3 pr-4">
                <span className="block font-medium text-slate-200">
                  {experiment.name}
                </span>
                <span className="text-xs text-slate-500">{experiment.method}</span>
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold ${evidenceTone(
                    experiment.evidence_kind,
                  )}`}
                >
                  {evidenceLabel(experiment.evidence_kind)}
                </span>
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold ${statusTone(
                    experiment.status,
                  )}`}
                >
                  {experiment.status}
                </span>
              </td>
              <td className="py-3 pr-4">{experiment.record_count}</td>
              <td className="py-3 pr-4 text-xs">
                {experiment.completed_at
                  ? new Date(experiment.completed_at).toLocaleString()
                  : "—"}
              </td>
              <td className="py-3">
                <button
                  type="button"
                  className={control}
                  disabled={busyId === experiment.id}
                  onClick={() => void onReport(experiment)}
                >
                  {busyId === experiment.id ? "Preparing…" : "Download JSON"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ValidationDashboard() {
  const { apiRequest, profile } = useAuth();
  const [overview, setOverview] = useState<ValidationOverview | null>(null);
  const [riskDetail, setRiskDetail] = useState<ValidationExperimentDetail | null>(null);
  const [correlationDetail, setCorrelationDetail] =
    useState<ValidationExperimentDetail | null>(null);
  const [decisionDetail, setDecisionDetail] =
    useState<ValidationExperimentDetail | null>(null);
  const [research, setResearch] = useState<Phase9Summary | null>(null);
  const [researchReport, setResearchReport] = useState<Phase9Report | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const next = await getValidationOverview(apiRequest);
    const [researchResult, reportResult] = await Promise.all([
      getPhase9Research(apiRequest).catch((researchFailure: unknown) => {
        setResearchError(errorMessage(researchFailure));
        return null;
      }),
      getPhase9Report(apiRequest).catch(() => null),
    ]);
    setResearch(researchResult);
    setResearchReport(reportResult);
    if (researchResult) setResearchError(null);
    const risk = next.experiments.find(
      (item) =>
        item.experiment_type === "RISK_BACKTEST" && item.status === "COMPLETED",
    );
    const correlation = next.experiments.find(
      (item) => item.experiment_type === "CORRELATION_SYNTHETIC",
    );
    const decision = next.experiments.find(
      (item) => item.experiment_type === "DECISION_SIMULATION",
    );
    const [riskResult, correlationResult, decisionResult] = await Promise.all([
      risk ? getValidationExperiment(apiRequest, risk.id) : Promise.resolve(null),
      correlation
        ? getValidationExperiment(apiRequest, correlation.id)
        : Promise.resolve(null),
      decision ? getValidationExperiment(apiRequest, decision.id) : Promise.resolve(null),
    ]);
    setOverview(next);
    setRiskDetail(riskResult);
    setCorrelationDetail(correlationResult);
    setDecisionDetail(decisionResult);
  }, [apiRequest]);

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

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await reload();
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function downloadReport(experiment: ValidationExperiment) {
    setBusy(experiment.id);
    setError(null);
    try {
      const report = await getValidationReport(apiRequest, experiment.id);
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${experiment.experiment_key}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reportError) {
      setError(errorMessage(reportError));
    } finally {
      setBusy(null);
    }
  }

  async function downloadPhase9Report() {
    setBusy("phase9-report");
    setError(null);
    try {
      const payload = researchReport ?? (await getPhase9Report(apiRequest));
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = payload.protocol_key + "-report.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reportError) {
      setError(errorMessage(reportError));
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8">
        <p className="text-sm text-slate-400" role="status">
          Loading persisted validation experiments…
        </p>
      </main>
    );
  }

  if (!overview) {
    return (
      <main className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8">
        <p className="rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {error ?? "Validation results are unavailable."}
        </p>
      </main>
    );
  }

  const dataset: ValidationDataset | undefined = overview.datasets[0];
  const latestRisk = riskDetail ?? overview.experiments.find(
    (item) => item.experiment_type === "RISK_BACKTEST",
  );
  const riskMetrics = asRecord(riskDetail?.metrics);
  const methods = asRecord(riskMetrics.methods);
  const riskMethod = asRecord(methods.civicflow_risk);
  const sensitivity = asRecord(riskMetrics.sensitivity);
  const windowSensitivity = asRecord(sensitivity.window_168_vs_336);
  const resolutionSensitivity = asRecord(sensitivity.resolution);
  const resolutionCounts = asRecord(resolutionSensitivity.cell_counts);
  const thresholdSensitivity = asRecord(sensitivity.thresholds);
  const thresholdCounts = asRecord(thresholdSensitivity.cell_counts_at_or_above);
  const density = asRecord(riskMetrics.density);
  const correlationMetrics = asRecord(correlationDetail?.metrics);
  const decisionMetrics = asRecord(decisionDetail?.metrics);
  const isAdmin = profile?.role === "ADMIN";

  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
            Phases 8–9 · validation &amp; model research
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            Validation &amp; urban data
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Persisted experiments only. Empirical service-request activity is
            labelled separately from synthetic fixtures and simulated planning.
            Phase 9 diagnosis and external holdout results are read from stored
            protocol rows; nothing here dispatches units, reserves resources, or
            mutates an incident.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={control}
            onClick={() => void run("refresh", async () => undefined)}
            disabled={busy !== null}
          >
            Refresh
          </button>
          <button
            type="button"
            className={control}
            onClick={() =>
              void run("correlation", () => runCorrelationValidation(apiRequest))
            }
            disabled={busy !== null}
          >
            {busy === "correlation" ? "Running…" : "Run synthetic correlation"}
          </button>
          <button
            type="button"
            className={control}
            onClick={() => void run("decision", () => runDecisionValidation(apiRequest))}
            disabled={busy !== null}
          >
            {busy === "decision" ? "Running…" : "Run planning simulation"}
          </button>
          {dataset ? (
            <button
              type="button"
              className={control}
              onClick={() =>
                void run("risk", () => runRiskValidation(apiRequest, dataset.id))
              }
              disabled={busy !== null}
            >
              {busy === "risk" ? "Backtesting…" : "Run temporal backtest"}
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="mt-5 rounded-xl border border-sky-300/25 bg-sky-300/10 p-4 text-sm text-sky-100">
        Evidence discipline: observational 311 complaint activity is not verified
        hazard impact; synthetic fixtures are not field ground truth; planning
        simulations are not realized outcomes. Read each experiment&apos;s
        limitations before citing a number.
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card
          label="Registered datasets"
          value={overview.datasets.length}
          detail={dataset ? `${dataset.record_count.toLocaleString()} records` : "No dataset"}
        />
        <Card
          label="Persisted experiments"
          value={overview.experiments.length}
          detail="Append-only run records"
        />
        <Card
          label="Latest risk PR-AUC"
          value={numberValue(riskMethod.pr_auc)}
          detail={latestRisk ? latestRisk.model_version ?? "risk model" : "No completed run"}
          tone={riskDetail ? "good" : "default"}
        />
        <Card
          label="Synthetic duplicate F1"
          value={numberValue(correlationMetrics.f1)}
          detail="Hand-labelled fixtures, not field labels"
          tone="warn"
        />
      </div>

      <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              Temporal risk backtest vs baselines
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Rolling-origin holdout. Only incidents available before each origin
              enter the model; the label is future activity in the next window.
            </p>
          </div>
          {latestRisk ? (
            <span className={`rounded-full border px-3 py-1 text-xs ${statusTone(latestRisk.status)}`}>
              {latestRisk.status}
            </span>
          ) : null}
        </div>
        {riskDetail ? (
          <div className="mt-4 space-y-4">
            <MethodTable metrics={riskMetrics} />
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                <p className="text-[10px] uppercase tracking-[0.15em] text-slate-500">
                  Window sensitivity (168h vs 336h)
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  Spearman {numberValue(windowSensitivity.spearman)} · top-20
                  Jaccard {numberValue(windowSensitivity.top20_jaccard)} ·{" "}
                  {numberValue(windowSensitivity.common_cell_count)} common cells
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                <p className="text-[10px] uppercase tracking-[0.15em] text-slate-500">
                  Resolution cell counts
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  H3-7 {numberValue(resolutionCounts["7"])} · H3-8{" "}
                  {numberValue(resolutionCounts["8"])} · H3-9{" "}
                  {numberValue(resolutionCounts["9"])}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Top-20 Jaccard H3-7 vs H3-8 parent:{" "}
                  {numberValue(resolutionSensitivity.top20_res7_vs_res8_parent_jaccard)}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Cells at/above risk bands: low {numberValue(thresholdCounts.low)} ·
                  moderate {numberValue(thresholdCounts.moderate)} · high{" "}
                  {numberValue(thresholdCounts.high)} · critical{" "}
                  {numberValue(thresholdCounts.critical)}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Density: {String(density.classification ?? "—")} · mean target
                  prevalence {numberValue(density.mean_label_prevalence)} · mean
                  universe cells {numberValue(density.mean_universe_cells)}
                </p>
              </div>
            </div>
            <ul className="space-y-2 text-sm leading-6 text-slate-300">
              {riskDetail.findings.map((finding) => (
                <li key={finding} className="rounded-lg bg-white/[0.03] px-3 py-2">
                  {finding}
                </li>
              ))}
            </ul>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300">
                Limitations
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-400">
                {riskDetail.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No completed empirical backtest is registered. Run one after
            registering a snapshot-backed dataset.
          </p>
        )}
      </section>

      <Phase9Research
        summary={research}
        report={researchReport}
        loading={false}
        error={researchError}
        onDownloadReport={() => void downloadPhase9Report()}
        busy={busy === "phase9-report"}
      />

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
          <h2 className="text-lg font-semibold text-white">Dataset provenance</h2>
          {dataset ? (
            <div className="mt-3 space-y-2 text-sm text-slate-300">
              <p className="font-medium text-slate-100">{dataset.name}</p>
              <p className="text-xs leading-5 text-slate-400">{dataset.description}</p>
              <p>
                <span className="text-slate-500">Region:</span> {dataset.region}
              </p>
              <p>
                <span className="text-slate-500">Period:</span>{" "}
                {dataset.period_start?.slice(0, 10) ?? "—"} to{" "}
                {dataset.period_end?.slice(0, 10) ?? "—"}
              </p>
              <p>
                <span className="text-slate-500">Records:</span>{" "}
                {dataset.record_count.toLocaleString()} · schema {dataset.schema_version}
              </p>
              <p className="break-all text-xs text-slate-500">
                SHA-256: {dataset.snapshot_sha256}
              </p>
              <a
                href={dataset.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex text-xs font-medium text-emerald-300 underline-offset-4 hover:underline"
              >
                Public source and portal terms
              </a>
              <p className="rounded-lg border border-white/10 bg-slate-950/40 p-3 text-xs leading-5 text-slate-400">
                {dataset.license_note}
              </p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">No dataset registered.</p>
          )}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
          <h2 className="text-lg font-semibold text-white">Synthetic evidence</h2>
          <div className="mt-3 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-300">
                Duplicate scoring · synthetic fixture
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-300">
                {correlationDetail
                  ? correlationDetail.findings[0] ?? "No findings recorded."
                  : "No synthetic correlation run recorded."}
              </p>
              {correlationDetail ? (
                <p className="mt-1 text-xs text-slate-500">
                  {correlationDetail.record_count} hand-labelled cases; suggestions
                  remain human-review only.
                </p>
              ) : null}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-violet-300">
                Decision planning · simulated
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-300">
                {decisionDetail
                  ? decisionDetail.findings[0] ?? "No findings recorded."
                  : "No planning simulation recorded."}
              </p>
              {decisionDetail ? (
                <p className="mt-1 text-xs text-slate-500">
                  Winner: {String(decisionMetrics.winner ?? "—")} · deterministic
                  repeat: {String(decisionMetrics.deterministic_schedule)}. No
                  dispatch or reservation.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <h2 className="text-lg font-semibold text-white">Experiment log</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          New runs create new keys. Reports are generated from the stored record,
          not recomputed from live incidents.
          {!isAdmin
            ? " Read access is available to workers; execution stays bounded."
            : null}
        </p>
        <div className="mt-4">
          <ExperimentRows
            experiments={overview.experiments}
            onReport={downloadReport}
            busyId={busy}
          />
        </div>
      </section>

      <p className="mt-6 text-xs leading-5 text-slate-500">
        {overview.limitations.join(" ")}
      </p>
    </main>
  );
}
