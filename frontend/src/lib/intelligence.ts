import type {
  ImpactPath,
  IncidentCandidate,
  RelationshipStatus,
  RelationshipType,
} from "@/types/intelligence";

export const relationshipTypeLabels: Record<RelationshipType, string> = {
  RELATED: "Related",
  DUPLICATE: "Duplicate",
  CONTEXT: "Context",
};

export const relationshipStatusLabels: Record<RelationshipStatus, string> = {
  CONFIRMED: "Confirmed by staff",
  DISMISSED: "Dismissed by staff",
};

export const impactTypeLabels: Record<ImpactPath["impact_type"], string> = {
  GEOSPATIAL_ASSOCIATION: "Spatial association",
  INFERRED_POTENTIAL: "Inferred potential",
};

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatDistance(value: number): string {
  if (value < 1000) {
    return `${Math.round(value)} m`;
  }
  return `${(value / 1000).toFixed(1)} km`;
}

export function formatTimeDelta(seconds: number): string {
  if (seconds < 3600) {
    return `${Math.max(1, Math.round(seconds / 60))} min`;
  }
  if (seconds < 86400) {
    return `${(seconds / 3600).toFixed(1)} h`;
  }
  return `${(seconds / 86400).toFixed(1)} d`;
}

export function candidateLabel(candidate: IncidentCandidate): string {
  return `${formatConfidence(candidate.confidence)} confidence · ${formatDistance(
    candidate.distance_m,
  )} away · ${formatTimeDelta(candidate.time_delta_seconds)} apart`;
}

export function confidenceTone(value: number): string {
  if (value >= 0.75) {
    return "text-amber-200 border-amber-300/30 bg-amber-300/10";
  }
  if (value >= 0.55) {
    return "text-sky-200 border-sky-300/30 bg-sky-300/10";
  }
  return "text-slate-300 border-white/10 bg-white/5";
}
