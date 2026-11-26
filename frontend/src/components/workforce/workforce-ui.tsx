import type { ReactNode } from "react";

import type {
  AssignmentStatus,
  WorkerApplicationStatus,
  WorkerStatus,
} from "@/types/workforce";

export const applicationStatusLabel: Record<WorkerApplicationStatus, string> = {
  PENDING: "Pending review",
  UNDER_REVIEW: "Under review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  ADDITIONAL_INFORMATION_REQUIRED: "Information required",
  SUSPENDED: "Suspended",
};

export const workerStatusLabel: Record<WorkerStatus, string> = {
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
};

export const assignmentStatusLabel: Record<AssignmentStatus, string> = {
  OFFERED: "Offered",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  IN_PROGRESS: "In progress",
  COMPLETION_SUBMITTED: "Awaiting verification",
  VERIFIED_COMPLETED: "Verified",
  CANCELLED: "Cancelled",
};

export type Tone = "neutral" | "good" | "warn" | "bad" | "info";

export function applicationTone(status: WorkerApplicationStatus): Tone {
  if (status === "APPROVED") return "good";
  if (status === "PENDING" || status === "UNDER_REVIEW") return "info";
  if (status === "ADDITIONAL_INFORMATION_REQUIRED") return "warn";
  return "bad";
}

export function assignmentTone(status: AssignmentStatus): Tone {
  if (status === "VERIFIED_COMPLETED") return "good";
  if (status === "ACCEPTED" || status === "IN_PROGRESS") return "info";
  if (status === "OFFERED") return "warn";
  if (status === "DECLINED" || status === "CANCELLED") return "bad";
  return "neutral";
}

const toneClasses: Record<Tone, string> = {
  neutral: "border-white/10 bg-white/5 text-slate-300",
  good: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  warn: "border-amber-400/25 bg-amber-400/10 text-amber-200",
  bad: "border-rose-400/25 bg-rose-400/10 text-rose-200",
  info: "border-sky-400/25 bg-sky-400/10 text-sky-200",
};

export function StatusPill({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}

export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-white/10 bg-slate-900/50 p-5 ${className}`}
    >
      {title ? (
        <h2 className="mb-4 text-sm font-semibold tracking-tight text-white">
          {title}
        </h2>
      ) : null}
      {children}
    </section>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-dashed border-white/10 px-4 py-8 text-center text-sm text-slate-500">
      {message}
    </p>
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
      className="flex flex-col gap-3 rounded-lg border border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-200 sm:flex-row sm:items-center sm:justify-between"
    >
      <span>{message}</span>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="self-start rounded-md border border-rose-400/30 px-3 py-1.5 text-xs font-medium transition hover:bg-rose-400/10"
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
      role="status"
      className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-4 py-6 text-sm text-slate-400"
    >
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-emerald-400/30 border-t-emerald-400"
      />
      {label}
    </div>
  );
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortId(value: string): string {
  return value.slice(0, 8);
}
