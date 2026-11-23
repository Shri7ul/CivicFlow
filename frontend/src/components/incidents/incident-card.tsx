import Link from "next/link";

import { StatusBadge, SeverityBadge } from "@/components/incidents/status-badge";
import { categoryLabels, formatDateTime } from "@/lib/incidents";
import type { Incident } from "@/types/incidents";

export function IncidentCard({ incident }: { incident: Incident }) {
  return (
    <Link
      href={`/incidents/${incident.id}`}
      className="group block rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/30 hover:bg-white/[0.05]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {categoryLabels[incident.category]}
          </p>
          <h2 className="mt-1 truncate text-base font-semibold text-white group-hover:text-emerald-100">
            {incident.title}
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={incident.status} />
          <SeverityBadge severity={incident.severity} />
        </div>
      </div>
      <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-400">
        {incident.description}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>{incident.address ?? "Location pinned"}</span>
        <span aria-hidden="true">·</span>
        <span>{formatDateTime(incident.created_at)}</span>
        {incident.assigned_department ? (
          <>
            <span aria-hidden="true">·</span>
            <span>{incident.assigned_department.name}</span>
          </>
        ) : null}
      </div>
    </Link>
  );
}
