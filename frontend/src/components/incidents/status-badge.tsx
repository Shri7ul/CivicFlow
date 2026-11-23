import type { IncidentSeverity, IncidentStatus } from "@/types/incidents";
import {
  severityLabels,
  severityTones,
  statusLabels,
  statusTones,
  toneClasses,
} from "@/lib/incidents";

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses[statusTones[status]]}`}
    >
      {statusLabels[status]}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: IncidentSeverity }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses[severityTones[severity]]}`}
    >
      {severityLabels[severity]}
    </span>
  );
}
