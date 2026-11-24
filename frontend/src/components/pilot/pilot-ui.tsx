"use client";

import type { ReactNode } from "react";

import type {
  CorrelationDecision,
  ReadinessCategory,
  ReadinessReport,
  ReadinessStatus,
} from "@/types/pilot";

const STATUS_STYLES: Record<string, string> = {
  PASS: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  READY_FOR_CONTROLLED_PILOT:
    "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  VERIFIED: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  ACCEPTED: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  DUPLICATE: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  ACTIVE: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  FAIL: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  BLOCKED: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  REJECTED: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  NEEDS_INVESTIGATION: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  NOT_READY: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  UNAVAILABLE: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  NOT_DUPLICATE: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  APPROVED: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  PENDING_APPROVAL: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  PENDING: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  IN_PROGRESS: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  IN_REVIEW: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  NEEDS_MORE_DATA: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  CONDITIONALLY_READY:
    "border-amber-400/30 bg-amber-400/10 text-amber-200",
  PAUSED: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  UNKNOWN: "border-slate-400/30 bg-slate-400/10 text-slate-300",
  NOT_ASSESSED: "border-slate-400/30 bg-slate-400/10 text-slate-300",
  UNREVIEWED: "border-slate-400/30 bg-slate-400/10 text-slate-300",
  NOT_APPLICABLE: "border-white/10 bg-white/5 text-slate-400",
  DRAFT: "border-white/10 bg-white/5 text-slate-300",
  COMPLETED: "border-white/10 bg-white/5 text-slate-300",
  ARCHIVED: "border-white/10 bg-white/5 text-slate-400",
};

const STATUS_LABELS: Record<string, string> = {
  NOT_ASSESSED: "Not assessed",
  IN_PROGRESS: "In progress",
  NOT_APPLICABLE: "Not applicable",
  NOT_READY: "Not ready",
  CONDITIONALLY_READY: "Conditionally ready",
  READY_FOR_CONTROLLED_PILOT: "Ready for controlled pilot",
  PENDING_APPROVAL: "Pending approval",
  NEEDS_INVESTIGATION: "Needs investigation",
  NEEDS_MORE_DATA: "Needs more data",
  IN_REVIEW: "In review",
  NOT_DUPLICATE: "Not duplicate",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  VERIFIED: "Verified metadata",
  UNAVAILABLE: "Unavailable",
};

export function humanStatus(value: string): string {
  return (
    STATUS_LABELS[value] ??
    value
      .toLowerCase()
      .replace(/_/g, " ")
      .replace(/^./, (letter) => letter.toUpperCase())
  );
}

export function StatusPill({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "border-white/10 bg-white/5 text-slate-300";
  return (
    <span
      className={
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide " +
        style
      }
    >
      {humanStatus(status)}
    </span>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatNumber(
  value: number | null | undefined,
  digits = 3,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Unknown";
  }
  return value.toFixed(digits);
}

export function decisionLabel(decision: CorrelationDecision): string {
  return humanStatus(decision);
}

export function Card({
  title,
  eyebrow,
  children,
  actions,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {eyebrow ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300/80">
              {eyebrow}
            </p>
          ) : null}
          <h3 className="mt-1 text-base font-semibold text-white">{title}</h3>
        </div>
        {actions}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-white/15 bg-slate-950/40 px-4 py-8 text-center">
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <p className="mx-auto mt-1 max-w-lg text-xs leading-relaxed text-slate-500">
        {hint}
      </p>
    </div>
  );
}

export function ErrorNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-400/20 bg-rose-400/5 px-4 py-3"
    >
      <p className="text-xs text-rose-200">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-rose-300/30 px-3 py-1.5 text-xs font-medium text-rose-100 transition hover:bg-rose-400/10"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-6 text-xs text-slate-400"
      role="status"
      aria-live="polite"
    >
      <span className="size-3 animate-pulse rounded-full bg-emerald-400/70" />
      {label}
    </div>
  );
}

function CategoryRow({ category }: { category: ReadinessCategory }) {
  return (
    <details className="group rounded-xl border border-white/10 bg-slate-950/40">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-4 py-3">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-100">
            {category.label}
          </span>
          {category.mandatory ? (
            <span className="text-[9px] uppercase tracking-wide text-slate-500">
              gate
            </span>
          ) : (
            <span className="text-[9px] uppercase tracking-wide text-slate-500">
              advisory
            </span>
          )}
        </span>
        <StatusPill status={category.status} />
      </summary>
      <div className="space-y-3 border-t border-white/5 px-4 py-3">
        <p className="text-xs leading-relaxed text-slate-400">
          {category.summary}
        </p>
        <ul className="space-y-2">
          {category.criteria.map((criterion) => (
            <li
              key={criterion.key}
              className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium text-slate-200">
                  {criterion.label}
                </span>
                <StatusPill status={criterion.status} />
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                {criterion.evidence}
              </p>
            </li>
          ))}
        </ul>
        {category.blocking_issues.length > 0 ? (
          <div className="rounded-lg border border-rose-400/20 bg-rose-400/5 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-rose-300">
              Blocking evidence
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] text-rose-100/80">
              {category.blocking_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <p className="text-[10px] text-slate-600">Owner: {category.owner}</p>
      </div>
    </details>
  );
}

export function ReadinessScorecard({
  report,
  title = "Pilot readiness scorecard",
  onExport,
}: {
  report: ReadinessReport;
  title?: string;
  onExport?: () => void;
}) {
  const status = report.overall as ReadinessStatus;
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300/80">
            Phase 11 readiness
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">
            {title}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Derived from persisted evidence at {formatDate(report.generated_at)}
            . Protocol {report.protocol}.
          </p>
        </div>
        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20"
          >
            Export scorecard JSON
          </button>
        ) : null}
      </div>

      <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-transparent p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Overall readiness
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-white">
              {humanStatus(report.overall)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={status} />
            <StatusPill
              status={report.ready_for_activation ? "PASS" : "BLOCKED"}
            />
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          {report.disclaimer}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["Pass", report.counts.PASS ?? 0],
            ["Fail", report.counts.FAIL ?? 0],
            ["Blocked", report.counts.BLOCKED ?? 0],
            ["Not assessed", report.counts.NOT_ASSESSED ?? 0],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-xl border border-white/5 bg-slate-950/40 px-3 py-2"
            >
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-0.5 text-lg font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[10px] text-slate-500">
          {report.counts.mandatory_total ?? 0} mandatory gates ·{" "}
          {report.counts.advisory_total ?? 0} advisory categories · activation
          remains a separate administrator action.
        </p>
      </div>

      {report.activation_blockers.length > 0 ? (
        <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.04] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-rose-300">
            Activation blockers ({report.activation_blockers.length})
          </p>
          <ul className="mt-2 grid gap-2 text-xs leading-relaxed text-rose-100/80 md:grid-cols-2">
            {report.activation_blockers.map((blocker) => (
              <li
                key={blocker}
                className="rounded-lg border border-rose-400/10 bg-slate-950/30 px-3 py-2"
              >
                {blocker}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-2 lg:grid-cols-2">
        {report.categories.map((category) => (
          <CategoryRow key={category.key} category={category} />
        ))}
      </div>
      <p className="text-[10px] leading-relaxed text-slate-600">
        {report.evidence_policy}
      </p>
    </section>
  );
}
