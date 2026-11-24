"use client";

import { useState } from "react";

import type {
  Phase9Report,
  Phase9Summary,
  ResearchDatasetSummary,
  ResearchInterval,
  ResearchPairedComparison,
  ResearchRobustnessRow,
} from "@/types/validation";

const control =
  "rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 disabled:opacity-50";

function value(input: number | null | undefined, digits = 3): string {
  if (typeof input !== "number" || !Number.isFinite(input)) return "—";
  // Keep small non-zero values visible instead of rounding them to "-0.000".
  const effective =
    input !== 0 && Math.abs(input) < 1 / 10 ** digits ? digits + 1 : digits;
  return input.toFixed(effective);
}

function signed(input: number | null | undefined, digits = 4): string {
  if (typeof input !== "number" || !Number.isFinite(input)) return "—";
  const effective =
    input !== 0 && Math.abs(input) < 1 / 10 ** digits ? digits + 1 : digits;
  return `${input > 0 ? "+" : ""}${input.toFixed(effective)}`;
}

function interval(block: ResearchInterval | null | undefined): string {
  if (!block || block.ci_low === null || block.ci_high === null) return "—";
  return `${value(block.ci_low)} – ${value(block.ci_high)}`;
}

function paired(block: ResearchPairedComparison | null | undefined): string {
  if (!block) return "—";
  return `${signed(block.mean_delta)} (${value(block.ci_low)} to ${value(block.ci_high)})`;
}

function Section({
  title,
  hint,
  aside,
  children,
}: {
  title: string;
  hint?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          {hint ? (
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{hint}</p>
          ) : null}
        </div>
        {aside}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="pb-2 pr-4 font-semibold">{children}</th>;
}

function RoleChip({ role }: { role: ResearchDatasetSummary["role"] }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
        role === "development"
          ? "border-sky-300/25 bg-sky-300/10 text-sky-200"
          : "border-slate-300/20 bg-slate-300/10 text-slate-300"
      }`}
    >
      {role === "development" ? "Development · selection" : "External holdout"}
    </span>
  );
}

function Verdict({ delta }: { delta: number | null }) {
  if (delta === null) {
    return <span className="text-xs text-slate-500">No comparison</span>;
  }
  const above = delta > 0;
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
        above
          ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-200"
          : "border-rose-300/25 bg-rose-300/10 text-rose-200"
      }`}
    >
      {above ? "Above best baseline" : "Below best baseline"}
    </span>
  );
}

function severityTone(severity: string): string {
  if (severity === "high") return "border-rose-300/25 bg-rose-300/10 text-rose-200";
  if (severity === "medium")
    return "border-amber-300/25 bg-amber-300/10 text-amber-200";
  return "border-sky-300/25 bg-sky-300/10 text-sky-200";
}

function RobustnessRows({
  rows,
  label,
  format,
}: {
  rows: ResearchRobustnessRow[];
  label: string;
  format: (row: ResearchRobustnessRow) => string;
}) {
  if (rows.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        No {label.toLowerCase()} variants recorded.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[540px] text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
          <tr>
            <Th>{label}</Th>
            <Th>PR-AUC</Th>
            <Th>ROC-AUC</Th>
            <Th>P@k</Th>
            <Th>Rank stability</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-300">
          {rows.map((row, index) => (
            <tr key={`${label}-${index}`}>
              <td className="py-2 pr-4 font-medium text-slate-200">{format(row)}</td>
              <td className="py-2 pr-4">{value(row.pr_auc)}</td>
              <td className="py-2 pr-4">{value(row.roc_auc)}</td>
              <td className="py-2 pr-4">{value(row.precision_at_k)}</td>
              <td className="py-2 text-xs text-slate-400">
                {row.mean_spearman === null && row.mean_top20_jaccard === null
                  ? "—"
                  : `ρ ${value(row.mean_spearman)} · Jaccard ${value(
                      row.mean_top20_jaccard,
                    )}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Phase9Research({
  summary,
  report,
  loading,
  error,
  onDownloadReport,
  busy,
}: {
  summary: Phase9Summary | null;
  report: Phase9Report | null;
  loading: boolean;
  error: string | null;
  onDownloadReport: () => void;
  busy: boolean;
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const datasets = summary?.datasets ?? [];
  const selected =
    datasets.find((item) => item.dataset_key === selectedKey) ?? datasets[0] ?? null;
  const decision = report?.model_changes ?? null;

  return (
    <section className="mt-8 rounded-3xl border border-emerald-300/15 bg-emerald-300/[0.03] p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
            Phase 9 · model diagnosis &amp; external validation
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
            Research evidence
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Persisted research experiments only. Every figure below is read from
            append-only validation records; nothing is recomputed in the browser
            and no model configuration was activated by this protocol.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {summary ? (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold text-slate-300">
              {summary.protocol_key}
            </span>
          ) : null}
          <button
            type="button"
            className={control}
            onClick={onDownloadReport}
            disabled={busy || !report}
          >
            {busy ? "Preparing…" : "Download Phase 9 report"}
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="mt-4 text-sm text-slate-400" role="status">
          Loading persisted Phase 9 research…
        </p>
      ) : null}

      {!loading && (!summary || datasets.length === 0) ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/40 p-4">
          <p className="text-sm font-medium text-slate-200">
            No Phase 9 research is persisted yet.
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            The workspace shows nothing rather than placeholders. Run the bounded
            protocol from the backend CLI and reload:
          </p>
          <code className="mt-2 block overflow-x-auto rounded-lg bg-black/40 px-3 py-2 text-xs text-emerald-200">
            .venv/Scripts/python.exe scripts/run_phase9_research.py --all
          </code>
        </div>
      ) : null}

      {datasets.length > 0 ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Snapshots evaluated
              </p>
              <p className="mt-1 text-2xl font-semibold text-white">{datasets.length}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {datasets.filter((item) => item.role === "external").length} external ·{" "}
                {datasets.filter((item) => item.role === "development").length} development
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Mean PR-AUC
              </p>
              <p className="mt-1 text-2xl font-semibold text-white">
                {value(summary?.mean_pr_auc_across_datasets)}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Pooled mean across datasets, not a confidence statement
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Beats strongest baseline
              </p>
              <p className="mt-1 text-2xl font-semibold text-amber-200">
                {
                  datasets.filter(
                    (item) =>
                      item.risk.pr_auc !== null &&
                      item.best_baseline?.pr_auc !== null &&
                      item.best_baseline !== null &&
                      item.risk.pr_auc > (item.best_baseline?.pr_auc ?? Infinity),
                  ).length
                }
                <span className="text-base text-slate-500"> / {datasets.length}</span>
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Counting datasets, not independent trials
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Candidate model
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-200">
                {summary?.selection.candidate_key ?? "None selected"}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {decision
                  ? decision.activation_state.replaceAll("_", " ").toLowerCase()
                  : "activation state unavailable"}
              </p>
            </div>
          </div>

          {report && report.executive_summary.length > 0 ? (
            <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-300">
              {report.executive_summary.map((line) => (
                <li key={line} className="rounded-lg bg-white/[0.03] px-3 py-2">
                  {line}
                </li>
              ))}
            </ul>
          ) : null}

          <Section
            title="Multi-region and multi-period evaluation"
            hint="Same metric definition, top-k, and rolling-origin protocol per snapshot. The development dataset alone informs candidate selection; external results are holdouts."
            aside={
              <span className="rounded-full border border-sky-300/25 bg-sky-300/10 px-3 py-1 text-[10px] font-semibold text-sky-200">
                Empirical observational · complaint activity
              </span>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-left text-sm">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <Th>Dataset</Th>
                    <Th>Role</Th>
                    <Th>Period</Th>
                    <Th>Records</Th>
                    <Th>PR-AUC</Th>
                    <Th>ROC-AUC</Th>
                    <Th>Best baseline</Th>
                    <Th>Δ vs best</Th>
                    <Th>Verdict</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-slate-300">
                  {datasets.map((item) => {
                    const delta =
                      item.risk.pr_auc !== null && item.best_baseline?.pr_auc !== null
                        ? item.risk.pr_auc - (item.best_baseline?.pr_auc ?? 0)
                        : null;
                    const prBlock = item.statistics.fold_intervals?.pr_auc;
                    return (
                      <tr key={item.dataset_key}>
                        <td className="py-3 pr-4">
                          <span className="block font-medium text-slate-200">
                            {item.dataset_key}
                          </span>
                          <span className="text-xs text-slate-500">
                            {item.density.classification ?? "—"} · {item.risk.fold_count ?? "—"}{" "}
                            folds
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <RoleChip role={item.role} />
                        </td>
                        <td className="py-3 pr-4 text-xs text-slate-400">
                          {item.period_start?.slice(0, 10) ?? "—"} to{" "}
                          {item.period_end?.slice(0, 10) ?? "—"}
                        </td>
                        <td className="py-3 pr-4">{item.record_count.toLocaleString()}</td>
                        <td className="py-3 pr-4">
                          {value(item.risk.pr_auc)}
                          <span className="block text-[11px] text-slate-500">
                            CI {interval(prBlock)}
                          </span>
                        </td>
                        <td className="py-3 pr-4">{value(item.risk.roc_auc)}</td>
                        <td className="py-3 pr-4 text-xs">
                          {item.best_baseline
                            ? `${item.best_baseline.method.replaceAll("_", " ")} · ${value(
                                item.best_baseline.pr_auc,
                              )}`
                            : "No baseline"}
                        </td>
                        <td className="py-3 pr-4">{signed(delta)}</td>
                        <td className="py-3">
                          <Verdict delta={delta} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Complaint activity measures reporting behaviour as well as urban
              conditions. A higher PR-AUC means better ranking of next-window
              activity; it is not evidence of prevented harm.
            </p>
          </Section>

          <Section
            title="Diagnostic detail"
            hint="Availability, target association, and redundancy of each configured factor, with the hypotheses the audit recorded."
            aside={
              <div className="flex flex-wrap gap-1">
                {datasets.map((item) => (
                  <button
                    key={item.dataset_key}
                    type="button"
                    aria-pressed={selected?.dataset_key === item.dataset_key}
                    className={`rounded-lg border px-2 py-1 text-[10px] font-medium ${
                      selected?.dataset_key === item.dataset_key
                        ? "border-emerald-300/30 bg-emerald-300/10 text-emerald-200"
                        : "border-white/10 bg-white/5 text-slate-400"
                    }`}
                    onClick={() => setSelectedKey(item.dataset_key)}
                  >
                    {item.dataset_key}
                  </button>
                ))}
              </div>
            }
          >
            {selected ? (
              <div className="space-y-4">
                <ul className="space-y-2">
                  {selected.diagnostics.hypotheses.length === 0 ? (
                    <li className="text-xs text-slate-500">No hypotheses recorded.</li>
                  ) : (
                    selected.diagnostics.hypotheses.map((item) => (
                      <li
                        key={`${item.severity}-${item.finding}`}
                        className="rounded-xl border border-white/10 bg-slate-950/40 p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${severityTone(
                              item.severity,
                            )}`}
                          >
                            {item.severity}
                          </span>
                          <p className="text-sm font-medium text-slate-200">
                            {item.finding}
                          </p>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-slate-400">
                          {item.evidence}
                        </p>
                      </li>
                    ))
                  )}
                </ul>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <Th>Factor</Th>
                        <Th>Availability</Th>
                        <Th>Target Spearman</Th>
                        <Th>Mean normalized</Th>
                        <Th>Zero share</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300">
                      {Object.entries(selected.diagnostics.factor_diagnostics).map(
                        ([factor, diagnostic]) => (
                          <tr key={factor}>
                            <td className="py-2 pr-4 font-medium text-slate-200">
                              {factor.replaceAll("_", " ")}
                            </td>
                            <td className="py-2 pr-4">
                              {(diagnostic.availability_rate * 100).toFixed(1)}%
                              <span className="block text-[11px] text-slate-500">
                                {diagnostic.available_count} / {diagnostic.observations}
                              </span>
                            </td>
                            <td className="py-2 pr-4">
                              {value(diagnostic.target_spearman)}
                            </td>
                            <td className="py-2 pr-4">
                              {value(diagnostic.mean_normalized)}
                            </td>
                            <td className="py-2">{value(diagnostic.zero_share)}</td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
                {Object.keys(selected.diagnostics.band_distribution).length > 0 ? (
                  <p className="text-xs text-slate-500">
                    Score bands in the audit:{" "}
                    {Object.entries(selected.diagnostics.band_distribution)
                      .map(
                        ([band, bandValue]) =>
                          `${band} ${bandValue.count} (${(bandValue.share * 100).toFixed(1)}%)`,
                      )
                      .join(" · ")}
                  </p>
                ) : null}
              </div>
            ) : null}
          </Section>

          <Section
            title="Factor ablation"
            hint="Each leave-one-out variant removes one factor and renormalizes the remaining weights. Deltas are paired against the full model on identical folds; intervals are descriptive."
            aside={
              selected ? (
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold text-slate-300">
                  {selected.dataset_key}
                </span>
              ) : null
            }
          >
            {selected && selected.ablation.variants.length > 0 ? (
              <div className="space-y-3">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[860px] text-left text-sm">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <Th>Variant</Th>
                        <Th>PR-AUC</Th>
                        <Th>Δ vs full</Th>
                        <Th>Wins / losses</Th>
                        <Th>Sign-test p</Th>
                        <Th>Status</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300">
                      {selected.ablation.variants
                        .filter((variant) => variant.kind !== "single_factor")
                        .sort(
                          (left, right) =>
                            (right.mean_delta ?? -9) - (left.mean_delta ?? -9),
                        )
                        .map((variant) => {
                          const chosen =
                            summary?.selection.candidate_key === variant.variant_key;
                          const excluded =
                            variant.ci_low !== null &&
                            variant.ci_high !== null &&
                            (variant.ci_low > 0 || variant.ci_high < 0);
                          const noDifference =
                            (variant.wins ?? 0) === 0 &&
                            (variant.losses ?? 0) === 0 &&
                            variant.mean_delta === 0;
                          return (
                            <tr key={variant.variant_key}>
                              <td className="py-2 pr-4 font-medium text-slate-200">
                                {variant.variant_key.replaceAll("_", " ")}
                                {chosen ? (
                                  <span className="ml-2 rounded-full border border-emerald-300/25 bg-emerald-300/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
                                    selected candidate
                                  </span>
                                ) : null}
                              </td>
                              <td className="py-2 pr-4">
                                {value(variant.pr_auc, 6)}
                              </td>
                              <td className="py-2 pr-4">
                                {signed(variant.mean_delta, 6)}
                                <span className="block text-[11px] text-slate-500">
                                  CI {value(variant.ci_low)} to {value(variant.ci_high)}
                                </span>
                              </td>
                              <td className="py-2 pr-4">
                                {variant.wins ?? "—"} / {variant.losses ?? "—"}
                              </td>
                              <td className="py-2 pr-4">{value(variant.sign_test_p)}</td>
                              <td className="py-2 text-xs">
                                {noDifference ? (
                                  <span className="text-slate-500">
                                    no fold-level difference
                                  </span>
                                ) : excluded ? (
                                  <span className="text-amber-200">
                                    interval excludes zero
                                  </span>
                                ) : (
                                  <span className="text-slate-500">
                                    interval includes zero
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs leading-5 text-slate-500">
                  Best variant by mean PR-AUC:{" "}
                  <span className="text-slate-300">
                    {selected.ablation.best_variant ?? "—"}
                  </span>{" "}
                  (Δ {signed(selected.ablation.best_minus_full_pr_auc, 6)} vs full).{" "}
                  {selected.ablation.interpretation}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No ablation run recorded.</p>
            )}
          </Section>

          <Section
            title="Sensitivity and robustness"
            hint="Resolution, target window, record thinning, density strata, and threshold bands. Cross-setting metrics are not strictly paired because the prediction universe changes."
          >
            {selected ? (
              <div className="space-y-5">
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                      H3 resolution
                    </p>
                    <div className="mt-2">
                      <RobustnessRows
                        rows={selected.robustness.resolution}
                        label="Resolution"
                        format={(row) =>
                          `H3-${row.resolution} · ${value(row.cell_count, 1)} cells`
                        }
                      />
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                      Target window
                    </p>
                    <div className="mt-2">
                      <RobustnessRows
                        rows={selected.robustness.target_window}
                        label="Window"
                        format={(row) => `${row.target_hours}h target`}
                      />
                    </div>
                  </div>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                      Record thinning
                    </p>
                    <div className="mt-2">
                      <RobustnessRows
                        rows={selected.robustness.record_thinning}
                        label="Retained"
                        format={(row) =>
                          `${Math.round((row.retained_fraction ?? 0) * 100)}% · ${row.retained_records ?? "—"} records`
                        }
                      />
                    </div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                      Density strata
                    </p>
                    <div className="mt-2 space-y-1 text-sm text-slate-300">
                      <p>
                        Dense PR-AUC {value(selected.robustness.density_strata.dense?.pr_auc)} ·
                        sparse PR-AUC{" "}
                        {value(selected.robustness.density_strata.sparse?.pr_auc)}
                      </p>
                      <p className="text-xs text-slate-500">
                        {selected.robustness.density_strata.note}
                      </p>
                      <p className="text-xs text-slate-500">
                        Descriptor missing{" "}
                        {value(
                          Number(selected.robustness.missingness.descriptor_missing_rate),
                          3,
                        )}
                        {" · "}borough missing{" "}
                        {value(Number(selected.robustness.missingness.borough_missing_rate), 3)}
                      </p>
                    </div>
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                    Threshold bands (ranking unchanged)
                  </p>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full min-w-[620px] text-left text-sm">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <Th>Threshold set</Th>
                          <Th>Cells</Th>
                          <Th>Band counts</Th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5 text-slate-300">
                        {Object.entries(
                          selected.robustness.threshold_sensitivity.variants ?? {},
                        ).map(([name, variant]) => (
                          <tr key={name}>
                            <td className="py-2 pr-4 font-medium text-slate-200">{name}</td>
                            <td className="py-2 pr-4">{variant.cell_total}</td>
                            <td className="py-2 text-xs">
                              {Object.entries(variant.cell_counts)
                                .map(([band, count]) => `${band} ${count}`)
                                .join(" · ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}
          </Section>

          <Section
            title="Statistical uncertainty"
            hint="Percentile bootstrap over rolling-origin folds. Folds overlap in time and cells are not independent, so these intervals describe observed variability, not deployment confidence."
          >
            {selected ? (
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <Th>Metric</Th>
                        <Th>Mean</Th>
                        <Th>Bootstrap CI</Th>
                        <Th>n</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300">
                      {Object.entries(selected.statistics.fold_intervals ?? {}).map(
                        ([metric, block]) => (
                          <tr key={metric}>
                            <td className="py-2 pr-4 font-medium text-slate-200">
                              {metric.replaceAll("_", " ")}
                            </td>
                            <td className="py-2 pr-4">{value(block.mean)}</td>
                            <td className="py-2 pr-4">{interval(block)}</td>
                            <td className="py-2">{block.n}</td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <Th>Paired vs baseline</Th>
                        <Th>Mean Δ</Th>
                        <Th>W / L</Th>
                        <Th>p</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300">
                      {Object.entries(
                        selected.statistics.paired_pr_auc_vs_baselines ?? {},
                      ).map(([method, block]) => (
                        <tr key={method}>
                          <td className="py-2 pr-4 text-xs text-slate-300">
                            {method.replaceAll("_", " ")}
                          </td>
                          <td className="py-2 pr-4">
                            {signed(block.mean_delta)}
                            <span className="block text-[11px] text-slate-500">
                              CI {value(block.ci_low)} to {value(block.ci_high)}
                            </span>
                          </td>
                          <td className="py-2 pr-4">
                            {block.wins ?? "—"} / {block.losses ?? "—"}
                          </td>
                          <td className="py-2">{value(block.sign_test_p)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </Section>

          <Section
            title="Candidate evaluation and model decision"
            hint="Pre-registered rule: the best leave-one-out variant on the development dataset only, evaluated afterwards on external holdouts. Evaluation never activates a model."
            aside={
              <span className="rounded-full border border-amber-300/25 bg-amber-300/10 px-3 py-1 text-[10px] font-semibold text-amber-200">
                NOT_ACTIVATED
              </span>
            }
          >
            <div className="space-y-3">
              {summary ? (
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs leading-5 text-slate-400">
                  <p className="text-slate-300">{summary.selection.rule}</p>
                  <p className="mt-1">
                    Outcome:{" "}
                    <span className="text-slate-200">{summary.selection.reason}</span>
                  </p>
                  {summary.selection.selection_statistics ? (
                    <p className="mt-1">
                      Selection paired Δ {paired(summary.selection.selection_statistics)}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {decision ? (
                <p className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm leading-6 text-slate-300">
                  {decision.decision}
                </p>
              ) : (
                <p className="text-xs text-slate-500">
                  No persisted decision is available; no model change is claimed.
                </p>
              )}
              {datasets.some((item) => item.candidates.length > 0) ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] text-left text-sm">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <Th>Dataset</Th>
                        <Th>Sample</Th>
                        <Th>PR-AUC</Th>
                        <Th>Reference</Th>
                        <Th>Paired Δ (CI)</Th>
                        <Th>Activated</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300">
                      {datasets.flatMap((item) =>
                        item.candidates.map((candidate) => (
                          <tr key={`${item.dataset_key}-${candidate.variant_key}`}>
                            <td className="py-2 pr-4 font-medium text-slate-200">
                              {item.dataset_key}
                            </td>
                            <td className="py-2 pr-4 text-xs">
                              {candidate.sample === "selection"
                                ? "selection"
                                : "external holdout"}
                            </td>
                            <td className="py-2 pr-4">{value(candidate.metrics.pr_auc, 6)}</td>
                            <td className="py-2 pr-4">
                              {value(candidate.reference_metrics.pr_auc, 6)}
                            </td>
                            <td className="py-2 pr-4">
                              {signed(candidate.delta_pr_auc.mean_delta, 6)}
                              <span className="block text-[11px] text-slate-500">
                                CI {value(candidate.delta_pr_auc.ci_low)} to{" "}
                                {value(candidate.delta_pr_auc.ci_high)}
                              </span>
                            </td>
                            <td className="py-2 text-xs text-slate-500">
                              {candidate.activated ? "Yes" : "No"}
                            </td>
                          </tr>
                        )),
                      )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  No candidate variant was selected, so no holdout evaluation exists.
                </p>
              )}
              {decision ? (
                <p className="text-xs leading-5 text-slate-500">
                  {decision.governance_note}
                </p>
              ) : null}
            </div>
          </Section>

          <Section
            title="Evidence policy and limitations"
            hint="Labels follow the evidence classes used across the validation workspace; nothing here is verified municipal ground truth."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <ul className="space-y-2 text-sm leading-6 text-slate-300">
                {(summary?.evidence_policy ?? []).map((item) => (
                  <li key={item} className="rounded-lg bg-white/[0.03] px-3 py-2">
                    {item}
                  </li>
                ))}
              </ul>
              <div className="max-h-64 overflow-y-auto rounded-xl border border-white/10 bg-slate-950/40 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300">
                  Limitations
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-400">
                  {(report?.limitations ?? selected?.limitations ?? []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
            {report && report.future_research.length > 0 ? (
              <div className="mt-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-sky-300">
                  Future research
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-400">
                  {report.future_research.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Section>
        </>
      ) : null}
    </section>
  );
}