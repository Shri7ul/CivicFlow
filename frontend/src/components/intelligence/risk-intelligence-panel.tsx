"use client";

import {
  formatRiskConfidence,
  formatRiskScore,
} from "@/lib/risk";
import type { RiskConfig, RiskGeoJSON, RiskSummary } from "@/types/risk";

type Props = {
  config: RiskConfig | null;
  data: RiskGeoJSON | null;
  summary: RiskSummary | null;
};

/**
 * Makes the actual inference path judge-visible. CivicFlow currently uses a
 * deterministic weighted risk engine, not a trained statistical model, so the
 * UI says so explicitly instead of mislabelling rules as ML.
 */
export function RiskIntelligencePanel({ config, data, summary }: Props) {
  const topCell = summary?.top_cells?.[0] ?? null;
  const limitations = [
    ...(config?.limitations ?? []),
    ...(data?.limitations ?? []),
  ].filter((value, index, all) => all.indexOf(value) === index);

  return (
    <section
      aria-labelledby="intelligence-heading"
      className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Judge-visible intelligence
          </p>
          <h2
            id="intelligence-heading"
            className="mt-1 text-lg font-semibold text-white"
          >
            Intelligence &amp; model transparency
          </h2>
        </div>
        <span className="rounded-full border border-amber-300/25 bg-amber-300/10 px-3 py-1 text-[11px] font-medium text-amber-100">
          Deterministic rules · not a trained ML model
        </span>
      </div>

      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
        Risk cells are computed synchronously in the API worker from observed
        incident activity, category/severity weights, infrastructure exposure
        and history. Weather is separate advisory context and never changes a
        score automatically. The output is operational prioritisation, not a
        causal claim.
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <h3 className="text-xs font-semibold text-slate-200">Inference run</h3>
          <dl className="mt-3 space-y-2 text-[11px] text-slate-400">
            <div className="flex justify-between gap-3">
              <dt>Engine / version</dt>
              <dd className="font-mono text-slate-200">
                {data?.model_version ?? config?.model_version ?? "unavailable"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Config hash</dt>
              <dd className="font-mono text-slate-200">
                {(data?.config_hash ?? config?.config_hash ?? "—").slice(0, 16)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Last inference</dt>
              <dd className="text-slate-200">
                {data?.generated_at
                  ? new Date(data.generated_at).toLocaleString()
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Execution</dt>
              <dd className="text-slate-200">Synchronous API worker</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Cells scored</dt>
              <dd className="text-slate-200">{summary?.total_cells ?? "—"}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <h3 className="text-xs font-semibold text-slate-200">Input features</h3>
          <p className="mt-1 text-[10px] leading-4 text-slate-500">
            Deterministic weights from the active configuration
          </p>
          <ul className="mt-3 space-y-1.5 text-[11px] text-slate-300">
            {config
              ? Object.entries(config.factor_weights).map(([key, value]) => (
                  <li key={key} className="flex justify-between gap-3">
                    <span>{config.factor_labels[key] ?? key}</span>
                    <span className="font-mono text-slate-400">
                      {(value * 100).toFixed(0)}%
                    </span>
                  </li>
                ))
              : null}
          </ul>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <h3 className="text-xs font-semibold text-slate-200">
            Current output
          </h3>
          {topCell ? (
            <dl className="mt-3 space-y-2 text-[11px] text-slate-400">
              <div className="flex justify-between gap-3">
                <dt>Highest-score cell</dt>
                <dd className="font-mono text-slate-200">
                  {topCell.h3_cell_id.slice(0, 14)}…
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Risk score</dt>
                <dd className="text-slate-200">
                  {formatRiskScore(topCell.risk_score)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Category</dt>
                <dd className="text-slate-200">{topCell.risk_category}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Confidence</dt>
                <dd className="text-slate-200">
                  {formatRiskConfidence(topCell.confidence)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Incidents in window</dt>
                <dd className="text-slate-200">{topCell.incident_count}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-[11px] leading-5 text-slate-500">
              No scored cell is available for the current viewport. Pan, zoom
              out or widen the window to see an actual inference result.
            </p>
          )}
        </div>
      </div>

      {limitations.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <h3 className="text-xs font-semibold text-slate-200">
            Limitations and honest labelling
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-5 text-slate-400">
            {limitations.slice(0, 6).map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
