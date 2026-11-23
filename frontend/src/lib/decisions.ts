import type {
  DecisionStrategy,
  PlanAction,
  ResourceAvailability,
  ScenarioHazard,
  ScenarioStatus,
} from "@/types/decisions";

export const strategyLabels: Record<DecisionStrategy, string> = {
  PRIORITY: "Priority-first",
  RISK_REDUCTION: "Risk reduction",
  COST_EFFICIENT: "Cost efficient",
  BALANCED: "Balanced",
};

export const hazardLabels: Record<ScenarioHazard, string> = {
  FLOOD: "Flood",
  DRAINAGE: "Drainage",
  ROAD: "Road",
  FIRE: "Fire",
  HEALTH: "Health",
  UTILITY: "Utility",
  MULTI_HAZARD: "Multi-hazard",
  OTHER: "Other",
};

export const scenarioStatusLabels: Record<ScenarioStatus, string> = {
  DRAFT: "Draft",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  ARCHIVED: "Archived",
};

export const resourceStatusLabels: Record<ResourceAvailability, string> = {
  UNKNOWN: "Unknown availability",
  AVAILABLE: "Available",
  LIMITED: "Limited",
  UNAVAILABLE: "Unavailable",
  PLANNING_ASSUMPTION: "Planning assumption",
};

export const actionStatusLabels: Record<PlanAction["status"], string> = {
  SCHEDULED: "Scheduled",
  BLOCKED: "Blocked",
  DEFERRED: "Deferred",
  UNSCHEDULED: "Unscheduled",
};

export function scenarioStatusTone(status: ScenarioStatus): string {
  if (status === "ARCHIVED") return "border-white/10 bg-white/5 text-slate-400";
  if (status === "COMPLETED") {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  if (status === "FAILED") {
    return "border-rose-300/25 bg-rose-300/10 text-rose-200";
  }
  if (status === "RUNNING") {
    return "border-sky-300/25 bg-sky-300/10 text-sky-200";
  }
  return "border-amber-300/25 bg-amber-300/10 text-amber-100";
}

export function actionStatusTone(status: PlanAction["status"]): string {
  if (status === "SCHEDULED") {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  if (status === "DEFERRED") {
    return "border-amber-300/25 bg-amber-300/10 text-amber-100";
  }
  return "border-rose-300/25 bg-rose-300/10 text-rose-200";
}

export function resourceStatusTone(status: ResourceAvailability): string {
  if (status === "AVAILABLE") {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  if (status === "PLANNING_ASSUMPTION" || status === "LIMITED") {
    return "border-amber-300/25 bg-amber-300/10 text-amber-100";
  }
  if (status === "UNAVAILABLE") {
    return "border-rose-300/25 bg-rose-300/10 text-rose-200";
  }
  return "border-white/10 bg-white/5 text-slate-400";
}

export function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 60) return `${value} min`;
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Not estimated";
  return `$${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })}`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function objectiveLabel(key: string): string {
  return (
    {
      risk_reduction: "Risk reduction",
      action_coverage: "Action coverage",
      cost_efficiency: "Cost efficiency",
      time_efficiency: "Time efficiency",
    }[key] ?? key
  );
}
