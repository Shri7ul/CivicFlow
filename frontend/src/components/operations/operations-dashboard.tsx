"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  acknowledgeAlert,
  createAlertRule,
  createDataSource,
  decideReview,
  evaluateAlerts,
  getOperationsDashboard,
  listNotifications,
  listPendingReviews,
  resolveAlert,
} from "@/lib/api/operations";
import type {
  Dashboard,
  NotificationRecord,
  ReviewDecision,
  ReviewRecord,
} from "@/types/operations";

const control =
  "w-full rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-emerald-400/50";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load operations data.";
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
      {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
    </div>
  );
}

function statusTone(status: string): string {
  if (["HEALTHY", "APPROVED", "COMPLETED"].includes(status)) {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  if (["STALE", "DEGRADED", "WARNING", "REVISION_REQUESTED"].includes(status)) {
    return "border-amber-300/25 bg-amber-300/10 text-amber-200";
  }
  if (["UNKNOWN", "FAILED", "CRITICAL", "REJECTED", "UNAVAILABLE"].includes(status)) {
    return "border-rose-300/25 bg-rose-300/10 text-rose-200";
  }
  return "border-white/10 bg-white/5 text-slate-300";
}

export function OperationsDashboard() {
  const { apiRequest, profile } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceKey, setSourceKey] = useState("manual-feed");
  const [sourceName, setSourceName] = useState("Manual source");
  const [reliability, setReliability] = useState("UNVERIFIED");
  const [ruleName, setRuleName] = useState("Risk threshold");
  const [ruleThreshold, setRuleThreshold] = useState("65");
  const [ruleSeverity, setRuleSeverity] = useState("WARNING");

  const reload = useCallback(async () => {
    const [next, pending, nextNotifications] = await Promise.all([
      getOperationsDashboard(apiRequest),
      listPendingReviews(apiRequest),
      listNotifications(apiRequest),
    ]);
    setData(next);
    setReviews(pending);
    setNotifications(nextNotifications);
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

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await reload();
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setBusy(false);
    }
  }

  async function submitSource() {
    await run(() =>
      createDataSource(apiRequest, {
        source_key: sourceKey,
        name: sourceName,
        category: "municipal",
        access_method: "staff-authorised manual batch",
        reliability,
        adapter: "manual",
        freshness_target_minutes: 1440,
      }),
    );
  }

  async function submitRule() {
    await run(() =>
      createAlertRule(apiRequest, {
        name: ruleName,
        rule_type: "RISK_THRESHOLD",
        metric: "max_risk_score",
        operator: ">=",
        threshold_value: Number(ruleThreshold),
        severity: ruleSeverity,
        cooldown_minutes: 60,
        dedupe_window_minutes: 60,
      }),
    );
  }

  async function handleReview(reviewId: string, decision: ReviewDecision) {
    await run(() =>
      decideReview(
        apiRequest,
        reviewId,
        decision,
        decision === "APPROVED"
          ? "Approved for planning; execution remains disabled."
          : "Planning review decision recorded.",
      ),
    );
  }

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8">
        <p className="text-sm text-slate-400" role="status">
          Loading operations dashboard…
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8">
        <p className="rounded-xl border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-200">
          {error ?? "Operations data is unavailable."}
        </p>
      </main>
    );
  }

  const unread = notifications.filter((item) => item.read_at === null).length;
  const isAdmin = profile?.role === "ADMIN";
  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
            Phase 7 · operational maturity
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            Operations command view
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Real records only. This view reports incidents, current H3 risk,
            source freshness, model governance, alerts, planning activity, and
            pending human approvals.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void run(async () => undefined)}
            disabled={busy}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 disabled:opacity-50"
          >
            Refresh
          </button>
          <span className={`rounded-full border px-3 py-2 text-xs ${statusTone(data.health.database ? "HEALTHY" : "FAILED")}`}>
            API DB {data.health.database ? "healthy" : "unavailable"}
          </span>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="mt-5 rounded-xl border border-amber-300/25 bg-amber-300/10 p-4 text-sm text-amber-100">
        Operational safety: {data.safety.note} No dispatch, assignment,
        reservation, or incident mutation is available anywhere in this view.
      </div>

      <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card label="Incidents last 24h" value={data.incidents.last_24h} detail={`${data.incidents.by_status.OPEN ?? 0} open`} />
        <Card
          label="Current max risk"
          value={data.risk.max_score === null ? "n/a" : data.risk.max_score.toFixed(1)}
          detail={`${data.risk.cell_count} cells · ${data.risk.window_hours}h window`}
          tone={data.risk.available ? "good" : "warn"}
        />
        <Card
          label="Data sources needing attention"
          value={data.data_quality.stale_or_unknown}
          detail={`${data.data_quality.sources.length} registered sources`}
          tone={data.data_quality.stale_or_unknown > 0 ? "warn" : "good"}
        />
        <Card
          label="Pending approvals"
          value={data.planning.pending_review_count}
          detail={`${data.planning.scenario_count} scenarios · ${data.planning.simulation_count} simulations`}
          tone={data.planning.pending_review_count > 0 ? "warn" : "good"}
        />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-lg font-semibold text-white">Risk distribution</h2>
          <p className="mt-1 text-xs text-slate-500">
            Current explainable model output, not a forecast.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
            {["MINIMAL", "LOW", "MODERATE", "HIGH", "CRITICAL"].map((band) => (
              <div key={band} className="rounded-lg border border-white/10 bg-slate-950/40 p-2">
                <p className="text-[10px] text-slate-500">{band}</p>
                <p className="text-lg font-semibold text-slate-100">{data.risk.bands[band] ?? 0}</p>
              </div>
            ))}
          </div>
          {data.data_quality.warnings.length > 0 ? (
            <div className="mt-4 space-y-1 rounded-lg border border-amber-300/20 bg-amber-300/5 p-3 text-xs text-amber-200">
              {data.data_quality.warnings.map((warning) => (
                <p key={warning}>• {warning}</p>
              ))}
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-lg font-semibold text-white">Model governance</h2>
          <p className="mt-1 text-xs text-slate-500">
            Active designation requires ADMIN activation and is recorded in the registry.
          </p>
          <div className="mt-3 space-y-2 text-sm">
            <p className="text-slate-300">
              Active risk model:{" "}
              <span className="font-medium text-white">
                {data.models.active_risk?.version ?? "runtime settings (not registered)"}
              </span>
            </p>
            <p className="text-slate-300">
              Active decision model:{" "}
              <span className="font-medium text-white">
                {data.models.active_decision?.version ?? "runtime settings (not registered)"}
              </span>
            </p>
            <p className="break-all text-xs text-slate-500">
              Config hash: {data.models.active_risk?.config_hash ?? "n/a"}
            </p>
            {data.models.latest_evaluation ? (
              <div className="mt-3 rounded-lg border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-400">
                <p className="font-medium text-slate-200">
                  Latest evaluation: {data.models.latest_evaluation.dataset_label}
                </p>
                <p className="mt-1">
                  {data.models.latest_evaluation.method} · {data.models.latest_evaluation.status} ·{" "}
                  {data.models.latest_evaluation.sample_count} samples
                  {data.models.latest_evaluation.is_synthetic ? " · SYNTHETIC FIXTURE" : ""}
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No evaluation records yet.</p>
            )}
          </div>
        </section>
      </div>
      <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Data quality and freshness</h2>
            <p className="mt-1 text-xs text-slate-500">
              Stale, invalid, duplicate, missing-field, and schema-change signals are explicit.
            </p>
          </div>
          {isAdmin ? (
            <div className="flex flex-wrap items-end gap-2">
              <input aria-label="Source key" className={control} value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="source key" />
              <input aria-label="Source name" className={control} value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="source name" />
              <select aria-label="Source reliability" className={control} value={reliability} onChange={(event) => setReliability(event.target.value)}>
                <option value="UNVERIFIED">Unverified</option>
                <option value="COMMUNITY">Community</option>
                <option value="VERIFIED">Verified</option>
                <option value="AUTHORITATIVE">Authoritative</option>
                <option value="PLANNING_ASSUMPTION">Planning assumption</option>
              </select>
              <button type="button" disabled={busy} onClick={() => void submitSource()} className="rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">
                Register source
              </button>
            </div>
          ) : null}
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-[10px] uppercase tracking-wider text-slate-500">
              <tr><th className="pb-2">Source</th><th className="pb-2">Reliability</th><th className="pb-2">Status</th><th className="pb-2">Freshness</th><th className="pb-2">Issues</th></tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {data.data_quality.sources.length === 0 ? (
                <tr><td colSpan={5} className="py-4 text-sm text-slate-500">No data sources registered. Nothing is treated as authoritative by default.</td></tr>
              ) : data.data_quality.sources.map((source) => (
                <tr key={source.source_id}>
                  <td className="py-3"><span className="font-medium text-slate-100">{source.name}</span><span className="block text-xs text-slate-500">{source.source_key}</span></td>
                  <td className="py-3 text-xs">{source.reliability}</td>
                  <td className="py-3"><span className={`rounded-full border px-2 py-1 text-[10px] ${statusTone(source.status)}`}>{source.status}</span></td>
                  <td className="py-3 text-xs">{source.freshness_minutes === null ? "unknown" : `${source.freshness_minutes} min`}</td>
                  <td className="py-3 text-xs text-amber-200/80">{source.issues.join(" ") || "none"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><h2 className="text-lg font-semibold text-white">Alerts and notifications</h2><p className="mt-1 text-xs text-slate-500">Cooldown and deduplication are enforced server-side.</p></div>
            <button type="button" disabled={busy} onClick={() => void run(async () => { await evaluateAlerts(apiRequest); })} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 disabled:opacity-50">Evaluate rules</button>
          </div>
          <div className="mt-3 flex gap-2 text-xs text-slate-400">
            <span>{unread} unread in-app</span>
            <span>·</span>
            <span>{data.alerts.active_by_severity.CRITICAL ?? 0} critical active</span>
          </div>
          <ul className="mt-3 space-y-2">
            {data.alerts.recent.length === 0 ? <li className="text-sm text-slate-500">No alerts have been triggered.</li> : data.alerts.recent.map((alert) => (
              <li key={alert.id} className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs">
                <div className="flex flex-wrap justify-between gap-2"><span className="font-medium text-slate-100">{alert.title}</span><span className={`rounded-full border px-2 py-1 text-[10px] ${statusTone(alert.severity)}`}>{alert.severity}</span></div>
                <p className="mt-1 text-slate-400">{alert.message}</p>
                <div className="mt-2 flex gap-2">
                  {alert.status === "ACTIVE" ? <button type="button" disabled={busy} onClick={() => void run(() => acknowledgeAlert(apiRequest, alert.id))} className="rounded border border-white/10 px-2 py-1 text-[10px] text-slate-300">Acknowledge</button> : null}
                  {alert.status !== "RESOLVED" ? <button type="button" disabled={busy} onClick={() => void run(() => resolveAlert(apiRequest, alert.id))} className="rounded border border-white/10 px-2 py-1 text-[10px] text-slate-300">Resolve</button> : null}
                </div>
              </li>
            ))}
          </ul>
          {isAdmin ? (
            <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-white/5 pt-4">
              <input aria-label="Rule name" className={control} value={ruleName} onChange={(event) => setRuleName(event.target.value)} />
              <input aria-label="Risk threshold" type="number" className={control} value={ruleThreshold} onChange={(event) => setRuleThreshold(event.target.value)} />
              <select aria-label="Alert severity" className={control} value={ruleSeverity} onChange={(event) => setRuleSeverity(event.target.value)}><option>INFO</option><option>WARNING</option><option>CRITICAL</option></select>
              <button type="button" disabled={busy} onClick={() => void submitRule()} className="rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">Add rule</button>
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-lg font-semibold text-white">Plan approvals</h2>
          <p className="mt-1 text-xs text-slate-500">A second administrator records the decision. Approval is not execution.</p>
          <ul className="mt-3 space-y-2">
            {reviews.length === 0 ? <li className="text-sm text-slate-500">No pending plan reviews.</li> : reviews.map((review) => (
              <li key={review.id} className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs">
                <p className="font-medium text-slate-100">{review.title}</p>
                <p className="mt-1 text-slate-500">{review.status} · submitted by {review.submitted_by_name ?? "unknown"}</p>
                {isAdmin ? <div className="mt-2 flex gap-2"><button type="button" disabled={busy} onClick={() => void handleReview(review.id, "APPROVED")} className="rounded bg-emerald-400 px-2 py-1 text-[10px] font-semibold text-slate-950">Approve</button><button type="button" disabled={busy} onClick={() => void handleReview(review.id, "REVISION_REQUESTED")} className="rounded border border-amber-300/30 px-2 py-1 text-[10px] text-amber-200">Request revision</button><button type="button" disabled={busy} onClick={() => void handleReview(review.id, "REJECTED")} className="rounded border border-rose-300/30 px-2 py-1 text-[10px] text-rose-200">Reject</button></div> : null}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <p className="mt-6 text-xs text-slate-500">
        Snapshot generated {new Date(data.generated_at).toLocaleString()} · environment {data.health.app_env} · no real-world dispatch or resource execution is enabled.
      </p>
    </main>
  );
}
