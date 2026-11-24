"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  Card,
  EmptyState,
  ErrorNotice,
  LoadingBlock,
  StatusPill,
  formatDate,
  formatNumber,
} from "@/components/pilot/pilot-ui";
import {
  getEvidenceSnapshot,
  getEvidenceSnapshots,
  getEvidenceWorkspace,
} from "@/lib/api/evidence";
import type {
  CorrelationUniverseSummary,
  EvidenceProvenance,
  EvidenceSnapshot,
  EvidenceWorkspace,
  ExternalResult,
  GroundTruthRecord,
  InfrastructureCoverageContext,
} from "@/types/evidence";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

function shortHash(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  return value.slice(0, 12) + "…" + value.slice(-8);
}

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Not assessed";
  return (value * 100).toFixed(1) + "%";
}

type ProvenanceBadgeValue = EvidenceProvenance | "OPERATIONAL";

const PROVENANCE_STYLES: Record<ProvenanceBadgeValue, string> = {
  REAL: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  OPERATIONAL: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  SYNTHETIC: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  SIMULATED: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  MIXED: "border-violet-400/30 bg-violet-400/10 text-violet-200",
  UNKNOWN: "border-slate-400/30 bg-slate-400/10 text-slate-300",
};

export function ProvenanceBadge({ value }: { value: ProvenanceBadgeValue }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide " +
        PROVENANCE_STYLES[value]
      }
    >
      {value}
    </span>
  );
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function EvidenceState({
  state,
  message,
  onRetry,
}: {
  state: "loading" | "empty" | "error";
  message?: string | null;
  onRetry?: () => void;
}) {
  if (state === "loading") {
    return <LoadingBlock label="Loading evidence ledger, provenance and validation results…" />;
  }
  if (state === "error") {
    return <ErrorNotice message={message ?? "The evidence ledger could not be loaded."} onRetry={onRetry} />;
  }
  return (
    <EmptyState
      title="No evidence workspace"
      hint="The server did not return an evidence ledger. This is not evidence of readiness."
    />
  );
}

export function EvidenceIntegritySummary({ workspace }: { workspace: EvidenceWorkspace }) {
  const integrity = workspace.evidence_integrity;
  const groundTruth = workspace.ground_truth;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-5" aria-label="Evidence integrity summary">
        <Metric label="Snapshots" value={integrity.snapshots} hint={integrity.current_snapshots + " current"} />
        <Metric label="Recomputed" value={integrity.automated_recomputations} hint="hash and count checks" />
        <Metric
          label="Verified ground truth"
          value={groundTruth.operational_verified_count}
          hint={groundTruth.human_verification === "NONE" ? "no human verification" : "operational records only"}
        />
        <Metric
          label="Infrastructure domains"
          value={workspace.infrastructure.domains_integrated + " / 7"}
          hint={workspace.infrastructure.assets_total + " active assets"}
        />
        <Metric
          label="Fresh external datasets"
          value={workspace.external_validation.registered_fresh_datasets}
          hint="post-Phase 9"
        />
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.04] p-4">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-300">
            Evidence blockers ({workspace.blockers.length})
          </h3>
          {workspace.blockers.length === 0 ? (
            <p className="mt-2 text-xs text-slate-300">No blockers are recorded.</p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-rose-100/80">
              {workspace.blockers.map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.03] p-4">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300">
            Not assessed
          </h3>
          {workspace.not_assessed.length === 0 ? (
            <p className="mt-2 text-xs text-slate-300">No not-assessed items are recorded.</p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-amber-100/80">
              {workspace.not_assessed.map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div>
        <h3 id={id} className="text-sm font-semibold tracking-tight text-white">
          {title}
        </h3>
        <p className="mt-1 max-w-3xl text-[11px] leading-relaxed text-slate-500">
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}

function SnapshotDetail({
  snapshot,
  loading,
  error,
}: {
  snapshot: EvidenceSnapshot | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <LoadingBlock label="Recomputing retained snapshot lineage…" />;
  if (error) return <ErrorNotice message={error} />;
  if (!snapshot) return null;
  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-white">{snapshot.snapshot_key}</p>
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceBadge value={snapshot.provenance} />
          <StatusPill status={snapshot.quality_status} />
          <StatusPill status={snapshot.verification_status} />
        </div>
      </div>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Provider", snapshot.provider],
          ["Dataset version", snapshot.dataset_version],
          ["Retrieved", formatDate(snapshot.retrieved_at)],
          ["Period", formatDate(snapshot.data_period_start) + " → " + formatDate(snapshot.data_period_end)],
          ["CRS", snapshot.crs ?? "Not declared"],
          ["Bounding box", snapshot.bbox.length === 4 ? snapshot.bbox.join(", ") : "Not available"],
          ["Raw rows", snapshot.raw_record_count],
          ["Normalized records", snapshot.record_count],
          ["Duplicates collapsed", snapshot.duplicate_count],
          ["Invalid omitted", snapshot.invalid_count],
          ["Missing fields", snapshot.missing_fields],
          ["Bytes retained", snapshot.byte_size],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1 break-words text-xs text-slate-200">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Hashes</p>
          <p className="mt-1 break-all font-mono text-[10px] text-slate-400">
            normalized: {snapshot.snapshot_sha256 ?? "not recorded"}
          </p>
          <p className="mt-1 break-all font-mono text-[10px] text-slate-400">
            raw: {snapshot.raw_sha256 ?? "not recorded"}
          </p>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            {snapshot.disclaimer}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Recomputation checks
          </p>
          {snapshot.verification_checks.length === 0 ? (
            <p className="mt-1 text-[11px] text-slate-500">No independent recomputation is recorded.</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {snapshot.verification_checks.map((check) => (
                <li key={check.check} className="flex flex-wrap items-start justify-between gap-2 text-[11px]">
                  <span className="text-slate-300">{check.check}</span>
                  <span className={check.status === "PASS" ? "text-emerald-300" : "text-rose-300"}>
                    {check.status}
                  </span>
                  <span className="w-full text-[10px] text-slate-500">{check.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Lineage</p>
          <p className="mt-1 break-all text-[11px] leading-relaxed text-slate-400">
            {JSON.stringify(snapshot.lineage_detail ?? snapshot.lineage)}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Quality checks</p>
          {snapshot.quality_checks.length === 0 ? (
            <p className="mt-1 text-[11px] text-slate-500">No quality checks recorded.</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {snapshot.quality_checks.map((check) => (
                <li key={check.check} className="text-[11px] text-slate-400">
                  <span className="font-medium text-slate-300">{check.check}</span>
                  {": "}{check.status} — {check.detail}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function GroundTruthTable({ records }: { records: GroundTruthRecord[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full min-w-[760px] text-left text-xs">
        <caption className="sr-only">Recent ground-truth assertions</caption>
        <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-3 py-2">Record</th>
            <th scope="col" className="px-3 py-2">Source type</th>
            <th scope="col" className="px-3 py-2">Status</th>
            <th scope="col" className="px-3 py-2">Provenance</th>
            <th scope="col" className="px-3 py-2">Evidence refs</th>
            <th scope="col" className="px-3 py-2">Created</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id} className="border-t border-white/5">
              <td className="px-3 py-2 font-mono text-[10px] text-slate-300">{record.record_key}</td>
              <td className="px-3 py-2 text-slate-300">{record.source_type}</td>
              <td className="px-3 py-2"><StatusPill status={record.status} /></td>
              <td className="px-3 py-2"><ProvenanceBadge value={record.provenance_kind} /></td>
              <td className="px-3 py-2 text-slate-400">{record.evidence_refs.length}</td>
              <td className="px-3 py-2 text-slate-400">{formatDate(record.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CorrelationCard({ universe }: { universe: CorrelationUniverseSummary }) {
  const metrics = universe.metrics;
  return (
    <Card
      title={universe.name}
      eyebrow={"Universe " + universe.version}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceBadge value={universe.provenance_kind} />
          <StatusPill status={universe.reference_complete ? "PASS" : "BLOCKED"} />
        </div>
      }
    >
      <p className="text-[11px] leading-relaxed text-slate-400">{universe.disclaimer}</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ["Candidates", universe.candidate_count],
          ["Reviewed", universe.reviewed_candidates],
          ["Reference size", universe.reference_size ?? "Unknown"],
          ["Reference complete", universe.reference_complete ? "Yes" : "No"],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-0.5 text-xs text-slate-200">{value}</dd>
          </div>
        ))}
      </dl>
      {metrics ? (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["Precision", metrics.metrics.precision],
            ["Recall", metrics.metrics.recall],
            ["F1", metrics.metrics.f1],
            ["True negatives", metrics.true_negatives],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-white/5 px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className="mt-0.5 text-xs text-slate-200">{value === null ? "Not computable" : formatNumber(value as number)}</dd>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.04] px-3 py-2 text-[11px] text-amber-100/80">
          Precision, recall, F1 and true negatives remain unavailable until a complete reference universe and independent reviewer labels exist.
        </p>
      )}
      {metrics ? <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{metrics.recall_reason}</p> : null}
    </Card>
  );
}

function InfrastructureContext({ context }: { context: InfrastructureCoverageContext | null }) {
  if (!context) {
    return <p className="text-[11px] text-slate-500">No descriptive infrastructure coverage context is available.</p>;
  }
  return (
    <div className="rounded-xl border border-sky-400/20 bg-sky-400/[0.03] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={context.status} />
        <span className="text-[10px] uppercase tracking-wide text-slate-500">
          Infrastructure-aware comparison: {context.infra_aware_comparison}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ["Bridge assets", context.bridge_assets],
          ["With coordinates", context.bridge_assets_with_coordinates],
          [
            "Requests in context",
            context.status === "DESCRIPTIVE_ONLY"
              ? context.incidents_within_radius + " / " + context.incidents
              : "Not assessed",
          ],
          [
            "Share within " + context.radius_m + " m",
            context.status === "DESCRIPTIVE_ONLY" ? percent(context.coverage) : "Not assessed",
          ],
          ["Median nearest bridge", context.median_nearest_bridge_m === null ? "Not assessed" : context.median_nearest_bridge_m + " m"],
          ["Dataset", context.dataset_key ?? "Unknown"],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-white/5 px-3 py-2">
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-0.5 text-xs text-slate-200">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{context.caveat}</p>
    </div>
  );
}

function ExternalTable({ rows }: { rows: ExternalResult[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full min-w-[860px] text-left text-xs">
        <caption className="sr-only">External validation results against strongest baselines</caption>
        <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-3 py-2">Dataset</th>
            <th scope="col" className="px-3 py-2">Freshness</th>
            <th scope="col" className="px-3 py-2">Records</th>
            <th scope="col" className="px-3 py-2">CivicFlow PR-AUC</th>
            <th scope="col" className="px-3 py-2">Strongest baseline</th>
            <th scope="col" className="px-3 py-2">Delta</th>
            <th scope="col" className="px-3 py-2">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.experiment_key} className="border-t border-white/5">
              <td className="px-3 py-2">
                <p className="font-medium text-slate-200">{row.dataset_key}</p>
                <p className="text-[10px] text-slate-500">{row.experiment_type}</p>
              </td>
              <td className="px-3 py-2 text-slate-400">{row.freshness_days === null ? "Unknown" : row.freshness_days + " days"}</td>
              <td className="px-3 py-2 text-slate-400">{row.record_count}</td>
              <td className="px-3 py-2 font-mono text-slate-300">{formatNumber(row.civicflow.pr_auc)}</td>
              <td className="px-3 py-2 text-slate-400">
                {row.strongest_baseline ?? "Not recorded"}
                <span className="ml-2 font-mono text-slate-500">{formatNumber(row.baselines[row.strongest_baseline ?? ""]?.pr_auc)}</span>
              </td>
              <td className={row.delta_pr_auc !== null && row.delta_pr_auc < 0 ? "px-3 py-2 font-mono text-rose-300" : "px-3 py-2 font-mono text-emerald-300"}>
                {row.delta_pr_auc === null ? "Unknown" : (row.delta_pr_auc > 0 ? "+" : "") + formatNumber(row.delta_pr_auc)}
              </td>
              <td className="px-3 py-2">
                <StatusPill status={row.beats_strongest_baseline === null ? "NOT_ASSESSED" : row.beats_strongest_baseline ? "PASS" : "FAIL"} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvidenceWorkspace() {
  const { apiRequest } = useAuth();
  const [workspace, setWorkspace] = useState<EvidenceWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [detail, setDetail] = useState<EvidenceSnapshot | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<EvidenceSnapshot[]>([]);
  const [snapshotTotal, setSnapshotTotal] = useState(0);
  const [moreLoading, setMoreLoading] = useState(false);

  const loadWorkspace = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setError(null);
        const result = await getEvidenceWorkspace(apiRequest, { signal });
        setWorkspace(result);
        setSnapshots(result.snapshots);
        setSnapshotTotal(result.evidence_integrity.snapshots);
      } catch (caught) {
        if (!signal?.aborted) setError(errorMessage(caught));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [apiRequest],
  );

  useEffect(() => {
    const controller = new AbortController();
    getEvidenceWorkspace(apiRequest, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        setWorkspace(result);
        setSnapshots(result.snapshots);
        setSnapshotTotal(result.evidence_integrity.snapshots);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [apiRequest]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await loadWorkspace();
    setRefreshing(false);
  }, [loadWorkspace]);

  const loadSnapshot = useCallback(
    async (snapshot: EvidenceSnapshot) => {
      setDetailId(snapshot.id);
      setDetailLoading(true);
      setDetailError(null);
      try {
        const result = await getEvidenceSnapshot(apiRequest, snapshot.id);
        setDetail(result);
      } catch (caught) {
        setDetail(null);
        setDetailError(errorMessage(caught));
      } finally {
        setDetailLoading(false);
      }
    },
    [apiRequest],
  );

  const loadMore = useCallback(async () => {
    if (moreLoading || snapshots.length >= snapshotTotal) return;
    setMoreLoading(true);
    try {
      const result = await getEvidenceSnapshots(apiRequest, {
        limit: 25,
        offset: snapshots.length,
      });
      setSnapshots((current) => {
        const known = new Set(current.map((item) => item.id));
        return [...current, ...result.items.filter((item) => !known.has(item.id))];
      });
      setSnapshotTotal(result.total);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setMoreLoading(false);
    }
  }, [apiRequest, moreLoading, snapshotTotal, snapshots.length]);

  const fresh = useMemo(
    () => workspace?.external_validation.results.filter((row) => row.classification === "FRESH_EXTERNAL_HOLDOUT") ?? [],
    [workspace],
  );
  const historical = useMemo(
    () => workspace?.external_validation.results.filter((row) => row.classification !== "FRESH_EXTERNAL_HOLDOUT") ?? [],
    [workspace],
  );

  if (loading) {
    return <EvidenceState state="loading" />;
  }
  if (error) {
    return <EvidenceState state="error" message={error} onRetry={() => void refresh()} />;
  }
  if (!workspace) {
    return <EvidenceState state="empty" />;
  }

  const integrity = workspace.evidence_integrity;
  const gt = workspace.ground_truth;
  const correlation = workspace.correlation;
  const infrastructure = workspace.infrastructure;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300/80">Phase 11 evidence ledger</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">Ground truth, provenance and external validation</h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-500">
            Every count below is derived from persisted snapshots, review records and validation experiments. REAL means bytes were acquired from the named public source and hashed; it does not mean CivicFlow field-verified physical condition.
          </p>
          <p className="mt-1 text-[10px] text-slate-600">Generated {formatDate(workspace.generated_at)} · protocol {workspace.protocol}</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={refreshing}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 disabled:opacity-50"
        >
          {refreshing ? "Refreshing…" : "Refresh ledger"}
        </button>
      </div>

      <EvidenceIntegritySummary workspace={workspace} />

      <Section
        id="phase11-datasets"
        title="Dataset registry"
        description="Canonical dataset versions with linked snapshot quality, freshness and explicit provenance. Historical Phase 9 datasets without a retained snapshot are shown as UNKNOWN, not silently relabelled REAL."
      >
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[880px] text-left text-xs">
            <caption className="sr-only">Dataset registry with provenance and snapshot status</caption>
            <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-3 py-2">Dataset</th>
                <th scope="col" className="px-3 py-2">Provenance</th>
                <th scope="col" className="px-3 py-2">Records</th>
                <th scope="col" className="px-3 py-2">Period</th>
                <th scope="col" className="px-3 py-2">Quality</th>
                <th scope="col" className="px-3 py-2">Freshness</th>
                <th scope="col" className="px-3 py-2">Role</th>
              </tr>
            </thead>
            <tbody>
              {workspace.dataset_registry.map((dataset) => (
                <tr key={dataset.dataset_key} className="border-t border-white/5">
                  <td className="px-3 py-2">
                    <p className="font-medium text-slate-200">{dataset.dataset_key}</p>
                    <p className="text-[10px] text-slate-500">{dataset.region}</p>
                  </td>
                  <td className="px-3 py-2"><ProvenanceBadge value={dataset.provenance} /></td>
                  <td className="px-3 py-2 text-slate-400">{dataset.record_count}</td>
                  <td className="px-3 py-2 text-slate-400">{formatDate(dataset.period_start)} → {formatDate(dataset.period_end)}</td>
                  <td className="px-3 py-2"><StatusPill status={dataset.quality} /></td>
                  <td className="px-3 py-2 text-slate-400">{dataset.freshness_days === null ? "Unknown" : dataset.freshness_days + " days"}</td>
                  <td className="px-3 py-2 text-slate-400">{dataset.external_role ? "Fresh external" : "Research or historical"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] leading-relaxed text-slate-500">{integrity.real_data_disclaimer}</p>
      </Section>

      <Section
        id="phase11-snapshots"
        title="Snapshots, hashes and lineage"
        description="Independent recomputation reads retained bytes and verifies normalized/raw SHA-256, record count, spatial extent and linked assets. It does not verify physical truth or replace human review."
      >
        {snapshots.length === 0 ? (
          <EmptyState title="No evidence snapshots" hint="No acquired dataset or infrastructure snapshot has been registered." />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[860px] text-left text-xs">
              <caption className="sr-only">Evidence snapshots with integrity and quality status</caption>
              <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-3 py-2">Snapshot</th>
                  <th scope="col" className="px-3 py-2">Kind</th>
                  <th scope="col" className="px-3 py-2">Records</th>
                  <th scope="col" className="px-3 py-2">Quality</th>
                  <th scope="col" className="px-3 py-2">Verification</th>
                  <th scope="col" className="px-3 py-2">SHA-256</th>
                  <th scope="col" className="px-3 py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snapshot) => (
                  <tr key={snapshot.id} className="border-t border-white/5 align-top">
                    <td className="px-3 py-2">
                      <p className="font-mono text-[10px] text-slate-200">{snapshot.snapshot_key}</p>
                      <p className="mt-1 text-[10px] text-slate-500">{snapshot.provider}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-400">{snapshot.kind === "INFRASTRUCTURE" ? "Infrastructure" : "Research dataset"}</td>
                    <td className="px-3 py-2 text-slate-400">{snapshot.record_count}</td>
                    <td className="px-3 py-2"><StatusPill status={snapshot.quality_status} /></td>
                    <td className="px-3 py-2"><StatusPill status={snapshot.verification_status} /></td>
                    <td className="px-3 py-2">
                      <span className="block font-mono text-[10px] text-slate-400" title={snapshot.snapshot_sha256 ?? undefined}>{shortHash(snapshot.snapshot_sha256)}</span>
                      <span className="mt-1 block text-[10px] text-slate-600">{snapshot.is_current ? "current" : "superseded"}</span>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() => void loadSnapshot(snapshot)}
                        aria-expanded={detailId === snapshot.id}
                        className="rounded-md border border-white/10 px-2 py-1 text-[10px] text-slate-300 hover:border-white/25"
                      >
                        {detailId === snapshot.id ? "Hide" : "Inspect"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {detailId ? <SnapshotDetail snapshot={detail} loading={detailLoading} error={detailError} /> : null}
        {snapshots.length < snapshotTotal ? (
          <button
            type="button"
            onClick={() => void loadMore()}
            disabled={moreLoading}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 disabled:opacity-50"
          >
            {moreLoading ? "Loading…" : "Load more snapshots"}
          </button>
        ) : null}
      </Section>

      <Section
        id="phase11-ground-truth"
        title="Ground-truth maturity"
        description="Citizen reports, AI predictions, human observations, independent evidence and official records remain distinct assertion types. Only a different staff reviewer can verify a record, and verification never changes the original report or any model score."
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {Object.entries(gt.status_counts).map(([status, count]) => (
            <div key={status} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">{status.replace(/_/g, " ")}</p>
              <p className="mt-0.5 text-lg font-semibold text-white">{count}</p>
            </div>
          ))}
        </div>
        <p className="text-[11px] leading-relaxed text-slate-400">
          Operational assertions: {gt.provenance_counts.OPERATIONAL ?? 0}. Synthetic test fixtures: {gt.provenance_counts.SYNTHETIC ?? 0}. Human verification: {gt.human_verification.toLowerCase()}. Synthetic fixtures are never pooled with operational evidence.
        </p>
        {gt.recent.length === 0 ? (
          <EmptyState title="No ground-truth assertions" hint="No citizen report, field observation or official record has been registered as a ground-truth assertion." />
        ) : (
          <GroundTruthTable records={gt.recent} />
        )}
        <details className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-300">Reviewer workflow and separation of duties</summary>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-500">
            {gt.workflow.map((step) => <li key={step}>{step}</li>)}
          </ul>
        </details>
      </Section>

      <Section
        id="phase11-correlation"
        title="Correlation review and agreement"
        description="Candidate labels are independent reviewer judgements, not physical truth. Recall, F1 and true negatives stay null unless a complete reference universe and all required labels exist."
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="Candidates" value={correlation.candidate_total} />
          <Metric label="Reviewed" value={correlation.reviewed_candidate_total} />
          <Metric label="Recall available" value={correlation.recall_available ? "Yes" : "No"} />
          <Metric label="True negatives" value={correlation.true_negatives_available ? "Available" : "Not computable"} />
        </div>
        {correlation.universes.length === 0 ? (
          <EmptyState title="No correlation universes" hint="No reference-complete universe has been attested, so recall and F1 cannot be computed." />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {correlation.universes.map((universe) => <CorrelationCard key={universe.id} universe={universe} />)}
          </div>
        )}
        <p className="text-[10px] leading-relaxed text-slate-500">{correlation.note}</p>
      </Section>

      <Section
        id="phase11-infrastructure"
        title="Infrastructure coverage"
        description="Only validated, current infrastructure snapshots with active assets count as integrated. One bridge domain is not full coverage; infrastructure-aware model comparison remains NOT_ASSESSED."
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="Domains integrated" value={infrastructure.domains_integrated + " / 7"} />
          <Metric label="Sources verified" value={infrastructure.domains_verified + " / 7"} />
          <Metric label="Active assets" value={infrastructure.assets_total} />
          <Metric label="Automated checks" value={infrastructure.independent_automated_checks} />
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {infrastructure.domains.map((domain) => (
            <div key={domain.domain} className="rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-slate-300">{domain.label}</span>
                <StatusPill status={domain.integrated_snapshot ? "PASS" : domain.verified_source ? "IN_PROGRESS" : "BLOCKED"} />
              </div>
              <p className="mt-1 text-[10px] text-slate-500">
                {domain.integrated_snapshot ? "Integrated snapshot" : domain.verified_source ? "Verified metadata only" : "No verified source"}
              </p>
            </div>
          ))}
        </div>
        {infrastructure.sources.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[760px] text-left text-xs">
              <caption className="sr-only">Infrastructure sources and validation state</caption>
              <thead className="bg-white/[0.04] text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-3 py-2">Source</th>
                  <th scope="col" className="px-3 py-2">Domain</th>
                  <th scope="col" className="px-3 py-2">Provider</th>
                  <th scope="col" className="px-3 py-2">Validation</th>
                  <th scope="col" className="px-3 py-2">Integrated</th>
                </tr>
              </thead>
              <tbody>
                {infrastructure.sources.map((source) => (
                  <tr key={source.source_key} className="border-t border-white/5">
                    <td className="px-3 py-2">
                      <p className="font-medium text-slate-200">{source.name}</p>
                      <p className="font-mono text-[10px] text-slate-500">{source.source_key}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-400">{source.category}</td>
                    <td className="px-3 py-2 text-slate-400">{source.provider}</td>
                    <td className="px-3 py-2"><StatusPill status={source.validation_status} /></td>
                    <td className="px-3 py-2 text-slate-400">{source.integrated ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <InfrastructureContext context={infrastructure.coverage_context} />
      </Section>

      <Section
        id="phase11-external"
        title="Fresh external validation"
        description="Post-Phase 9 NYC 311 slices are evaluated with the registered Phase 9 risk methodology and configuration. The holdout is not used for tuning; unfavorable results are retained and shown."
      >
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-[11px] leading-relaxed text-slate-400">
          <p>{workspace.external_validation.methodology}</p>
          <p className="mt-1 text-[10px] text-slate-500">{workspace.external_validation.baseline_note}</p>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-slate-200">Fresh external holdout</h4>
          {fresh.length === 0 ? (
            <EmptyState title="No fresh external result" hint="No post-Phase 9 external dataset has been evaluated." />
          ) : (
            <ExternalTable rows={fresh} />
          )}
        </div>
        <div>
          <h4 className="text-xs font-semibold text-slate-200">Historical or diagnostic comparisons</h4>
          {historical.length === 0 ? (
            <p className="text-[11px] text-slate-500">No historical comparison is registered.</p>
          ) : (
            <ExternalTable rows={historical} />
          )}
        </div>
        <p className="text-[10px] leading-relaxed text-slate-500">
          Confidence intervals are not reported for overlapping rolling-origin folds. Baseline selection uses observed holdout PR-AUC for reporting only; no model is activated or promoted by this workspace.
        </p>
      </Section>

      <p className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 text-[10px] leading-relaxed text-slate-500">
        {workspace.synthetic_separation}
      </p>
    </div>
  );
}