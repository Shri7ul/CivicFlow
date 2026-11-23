import type {
  IncidentCategory,
  IncidentSeverity,
  IncidentStatus,
} from "@/types/incidents";

type BadgeTone = "slate" | "emerald" | "amber" | "rose" | "sky" | "violet";

export const statusLabels: Record<IncidentStatus, string> = {
  OPEN: "Open",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
};

export const statusTones: Record<IncidentStatus, BadgeTone> = {
  OPEN: "amber",
  ACKNOWLEDGED: "sky",
  IN_PROGRESS: "violet",
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
      return ["ACKNOWLEDGED", "IN_PROGRESS"];
    case "ACKNOWLEDGED":
      return ["IN_PROGRESS"];
    case "IN_PROGRESS":
      return ["RESOLVED"];
    case "RESOLVED":
      return ["CLOSED"];
    case "CLOSED":
      return [];
  }
}
