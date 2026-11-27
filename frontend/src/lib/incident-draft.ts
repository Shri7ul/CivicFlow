import type { IncidentCategory, IncidentSeverity } from "@/types/incidents";

export const INCIDENT_DRAFT_KEY = "civicflow:incident-draft:v1";

export type IncidentDraft = {
  title: string;
  description: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  latitude: string;
  longitude: string;
  address: string;
};

const text = (value: unknown): string =>
  typeof value === "string" ? value : "";

/**
 * Restores an in-progress report after a tab change, map interaction or
 * accidental component remount. Stored only in this browser tab's
 * sessionStorage; never sent to the API and never cleared by a local UI
 * interaction other than a successful submission.
 */
export function readIncidentDraft(): Partial<IncidentDraft> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(INCIDENT_DRAFT_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const value = parsed as Record<string, unknown>;
    return {
      title: text(value.title),
      description: text(value.description),
      category: text(value.category) as IncidentCategory,
      severity: text(value.severity) as IncidentSeverity,
      latitude: text(value.latitude),
      longitude: text(value.longitude),
      address: text(value.address),
    };
  } catch {
    return {};
  }
}

export function writeIncidentDraft(draft: IncidentDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(INCIDENT_DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // Private-browsing storage failures must not block incident reporting.
  }
}

export function clearIncidentDraft(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(INCIDENT_DRAFT_KEY);
  } catch {
    // Nothing to do; the report has already been submitted.
  }
}
