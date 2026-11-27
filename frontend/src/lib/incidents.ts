import type {
  IncidentCategory,
  IncidentSeverity,
  IncidentStatus,
} from "@/types/incidents";

type BadgeTone = "slate" | "emerald" | "amber" | "rose" | "sky" | "violet";

export const statusLabels: Record<IncidentStatus, string> = {
  OPEN: "Open",
  VERIFIED: "Verified",
  ASSIGNED: "Assigned",
  ACCEPTED: "Accepted",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  COMPLETION_SUBMITTED: "Completion submitted",
  VERIFIED_COMPLETED: "Verified completed",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
};

export const statusTones: Record<IncidentStatus, BadgeTone> = {
  OPEN: "amber",
  VERIFIED: "sky",
  ASSIGNED: "violet",
  ACCEPTED: "violet",
  ACKNOWLEDGED: "sky",
  IN_PROGRESS: "violet",
  COMPLETION_SUBMITTED: "amber",
  VERIFIED_COMPLETED: "emerald",
  RESOLVED: "emerald",
  CLOSED: "slate",
};

export const severityLabels: Record<IncidentSeverity, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const severityTones: Record<IncidentSeverity, BadgeTone> = {
  LOW: "slate",
  MEDIUM: "sky",
  HIGH: "amber",
  CRITICAL: "rose",
};

export const categoryLabels: Record<IncidentCategory, string> = {
  ROADS: "Roads",
  DRAINAGE: "Drainage",
  SANITATION: "Sanitation",
  UTILITIES: "Utilities",
  PUBLIC_SAFETY: "Public safety",
  HEALTH: "Health",
  ENVIRONMENT: "Environment",
  OTHER: "Other",
};

export const categories = Object.keys(
  categoryLabels,
) as IncidentCategory[];
export const severities = Object.keys(
  severityLabels,
) as IncidentSeverity[];
export const statuses = Object.keys(statusLabels) as IncidentStatus[];

export const toneClasses: Record<BadgeTone, string> = {
  slate: "border-white/10 bg-white/5 text-slate-300",
  emerald: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-300/25 bg-amber-300/10 text-amber-200",
  rose: "border-rose-300/25 bg-rose-300/10 text-rose-200",
  sky: "border-sky-300/25 bg-sky-300/10 text-sky-200",
  violet: "border-violet-300/25 bg-violet-300/10 text-violet-200",
};

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatCoordinates(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

export function allowedNextStatuses(
  status: IncidentStatus,
): IncidentStatus[] {
  switch (status) {
    case "OPEN":
      return ["ACKNOWLEDGED", "IN_PROGRESS", "VERIFIED"];
    case "VERIFIED":
      return ["ASSIGNED", "OPEN"];
    case "ASSIGNED":
      return ["ACCEPTED", "VERIFIED"];
    case "ACCEPTED":
      return ["IN_PROGRESS", "ASSIGNED"];
    case "ACKNOWLEDGED":
      return ["IN_PROGRESS"];
    case "IN_PROGRESS":
      return ["RESOLVED", "COMPLETION_SUBMITTED", "ASSIGNED"];
    case "COMPLETION_SUBMITTED":
      return ["VERIFIED_COMPLETED", "IN_PROGRESS", "ASSIGNED"];
    case "VERIFIED_COMPLETED":
      return ["RESOLVED", "IN_PROGRESS"];
    case "RESOLVED":
      return ["CLOSED"];
    case "CLOSED":
      return [];
  }
}
