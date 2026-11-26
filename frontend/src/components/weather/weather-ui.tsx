import type { ReactNode } from "react";

import type {
  WeatherAssessment,
  WeatherSignal,
} from "@/types/weather";

export type WeatherVariant = "citizen" | "worker" | "admin";

export const weatherStatusLabel: Record<string, string> = {
  OK: "Assessed",
  STALE: "Stale · last known conditions",
  ERROR: "Unavailable",
  DISABLED: "Not enabled",
};

export function metric(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value}${unit}`;
}

export function timestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const tones: Record<string, string> = {
    neutral: "border-white/15 bg-white/5 text-slate-300",
    good: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    warn: "border-amber-400/25 bg-amber-400/10 text-amber-200",
    bad: "border-rose-400/25 bg-rose-400/10 text-rose-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function SignalRow({ signal }: { signal: WeatherSignal }) {
  return (
    <li className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-slate-400">
          {signal.rule_id}
        </span>
        <Pill tone={signal.relevance === "LIKELY" ? "warn" : "neutral"}>
          {signal.relevance.toLowerCase()}
        </Pill>
        <span className="text-[10px] uppercase tracking-[0.1em] text-slate-500">
          {signal.kind.replace("_", " ").toLowerCase()}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-300">
        {signal.explanation}
      </p>
    </li>
  );
}

export function WeatherAssessmentCard({
  assessment,
  variant,
  loading = false,
  error = null,
  onRetry,
  onRefresh,
  refreshing = false,
}: {
  assessment: WeatherAssessment | null;
  variant: WeatherVariant;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  return (
    <section
      id="weather-impact"
      className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8"
      aria-labelledby="weather-impact-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="weather-impact-heading"
            className="text-sm font-semibold text-white"
          >
            Weather impact context
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">
            Conditions near this incident may change its urgency. This is
            advisory context for review, not a confirmed cause or an automatic
            priority decision.
          </p>
        </div>
        {assessment ? (
          <div className="flex flex-wrap items-center gap-2">
            <Pill
              tone={
                assessment.status === "OK"
                  ? "good"
                  : assessment.status === "STALE"
                    ? "warn"
                    : "bad"
              }
            >
              {weatherStatusLabel[assessment.status] ?? assessment.status}
            </Pill>
            {assessment.stale ? <Pill tone="warn">stale</Pill> : null}
          </div>
        ) : null}
      </div>

      {loading && !assessment ? (
        <div className="mt-5 h-20 animate-pulse rounded-2xl bg-white/[0.04]" role="status">
          <span className="sr-only">Loading weather context</span>
        </div>
      ) : null}

      {error && !assessment ? (
        <div role="alert" className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-300/5 p-4">
          <p className="text-sm text-rose-100">{error}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white"
            >
              Retry weather context
            </button>
          ) : null}
        </div>
      ) : null}

      {!loading && !error && !assessment ? (
        <p className="mt-5 rounded-lg border border-dashed border-white/10 px-4 py-8 text-center text-sm text-slate-500">
          No weather assessment is available for this incident.
        </p>
      ) : null}

      {assessment && assessment.status !== "OK" ? (
        <div
          className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/5 p-4"
          role="status"
        >
          <p className="text-sm text-amber-100">
            {assessment.status === "STALE"
              ? "The last known weather context is shown below. A fresh update could not be retrieved, so treat it with care."
              : assessment.assessment.explanation ??
                "Weather context is unavailable for this incident."}
          </p>
          <p className="mt-2 text-xs text-slate-400">
            {assessment.assessment.uncertainty}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Last attempt: {timestamp(assessment.last_attempt_at)} · Source:{" "}
            {assessment.source_attribution}
          </p>
        </div>
      ) : null}

      {assessment && (assessment.status === "OK" || assessment.status === "STALE") ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                Temperature (observed)
              </p>
              <p className="mt-1 text-lg font-semibold text-white">
                {metric(assessment.weather_snapshot?.current?.temperature_c, "°C")}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                Precipitation (observed)
              </p>
              <p className="mt-1 text-lg font-semibold text-white">
                {metric(assessment.weather_snapshot?.current?.precipitation_mm, " mm")}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                Wind (observed)
              </p>
              <p className="mt-1 text-lg font-semibold text-white">
                {metric(assessment.weather_snapshot?.current?.wind_speed_kmh, " km/h")}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                Observed at
              </p>
              <p className="mt-1 text-sm text-white">
                {timestamp(assessment.weather_snapshot?.current?.observed_at)}
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Forecast
              </h3>
              <ul className="mt-3 space-y-2">
                {(assessment.weather_snapshot?.forecast ?? []).slice(0, 4).map(
                  (hour) => (
                    <li
                      key={hour.time}
                      className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs"
                    >
                      <span className="text-slate-400">{timestamp(hour.time)}</span>
                      <span className="text-slate-200">
                        {metric(hour.precipitation_mm, " mm")}
                      </span>
                      <span className="text-slate-400">
                        {metric(hour.precipitation_probability_pct, "% chance")}
                      </span>
                    </li>
                  ),
                )}
              </ul>
            </section>

            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Possible relevance
              </h3>
              <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-300">
                {assessment.assessment.potential_aggravation.map((item, index) => (
                  <li key={`aggravation-${index}`}>- {item}</li>
                ))}
                {assessment.assessment.potential_secondary_hazards.map(
                  (item, index) => (
                    <li key={`secondary-${index}`}>- {item}</li>
                  ),
                )}
                {assessment.assessment.context_notes.map((item, index) => (
                  <li key={`context-${index}`}>- {item}</li>
                ))}
                {assessment.assessment.signals.length === 0 ? (
                  <li className="text-slate-500">
                    No category-specific weather relevance was identified.
                  </li>
                ) : null}
              </ul>
            </section>
          </div>

          {variant === "admin" ? (
            <details className="mt-5 rounded-xl border border-white/10 bg-slate-950/40 p-4">
              <summary className="cursor-pointer text-xs font-semibold text-slate-200">
                Why this was flagged (rules and evidence)
              </summary>
              <ul className="mt-3 space-y-2">
                {assessment.assessment.signals.map((signal) => (
                  <SignalRow key={signal.rule_id} signal={signal} />
                ))}
                {assessment.assessment.signals.length === 0 ? (
                  <li className="text-xs text-slate-500">No rules triggered.</li>
                ) : null}
              </ul>
              <p className="mt-3 text-[11px] text-slate-500">
                Rule engine: {assessment.rule_engine_version} · Data quality:{" "}
                {assessment.weather_snapshot?.data_quality}
              </p>
            </details>
          ) : null}

          <div className="mt-5 rounded-xl border border-white/5 bg-white/[0.02] p-4 text-xs leading-5 text-slate-400">
            <p>{assessment.assessment.uncertainty}</p>
            <p className="mt-1">{assessment.assessment.decision_note}</p>
            <p className="mt-2 text-slate-500">
              Source: {assessment.source_attribution} · Retrieved:{" "}
              {timestamp(assessment.retrieved_at)} · Forecast window:{" "}
              {timestamp(assessment.forecast_from)} to{" "}
              {timestamp(assessment.forecast_to)}
            </p>
          </div>

          {variant === "admin" && onRefresh ? (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white transition hover:bg-white/5 disabled:opacity-50"
              >
                {refreshing ? "Refreshing…" : "Reassess weather"}
              </button>
              <span className="text-[11px] text-slate-500">
                Refresh contacts the provider once; cached data is used otherwise.
              </span>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
