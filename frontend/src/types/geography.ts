export interface GeographicContext {
  key: string;
  display_name: string;
  country_code: string;
  country_name: string;
  kind: string;
  bbox_geojson: number[];
  center_geojson: { latitude: number; longitude: number };
  crs: string;
  provenance_basis: string;
  boundary_basis: string;
  boundary_status: string;
  operational_authority: string | null;
  is_pilot_eligible: boolean;
  source_urls: string[];
  notes: string;
}

export interface GeographicContextList {
  items: GeographicContext[];
  count: number;
  disclaimer: string;
}

export interface ReadinessCriterion {
  key: string;
  label: string;
  status: string;
  blocking: boolean;
  evidence: string;
  evidence_refs: string[];
}

export interface ReadinessCategory {
  key: string;
  label: string;
  status: string;
  mandatory: boolean;
  owner: string;
  summary: string;
  criteria: ReadinessCriterion[];
  blocking_issues: string[];
}

export interface DhakaReadinessReport {
  protocol: string;
  generated_at: string;
  geographic_context_key: string;
  overall: string;
  pilot_activation_authorized: boolean;
  ready_for_activation: boolean;
  categories: ReadinessCategory[];
  mandatory_unmet: string[];
  advisory_unmet: string[];
  blockers: string[];
  disclaimer: string;
  pilot_area_selection: {
    status: string;
    selected_area: string | null;
    reason: string;
    candidates: Array<{
      name: string;
      context_key: string;
      bbox_geojson: number[];
      status: string;
      blockers: string[];
    }>;
  };
}

export interface PilotAreaSelection {
  status: string;
  selected_area: string | null;
  reason: string;
  candidates: Array<{
    name: string;
    context_key: string;
    bbox_geojson: number[];
    basis: string;
    status: string;
    rationale: string;
    blockers: string[];
  }>;
}
