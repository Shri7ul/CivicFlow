export type PilotStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "ACTIVE"
  | "PAUSED"
  | "COMPLETED"
  | "REJECTED"
  | "ARCHIVED";

export type PilotMode = "SIMULATION" | "STAGING";

export type ReadinessStatus =
  | "NOT_ASSESSED"
  | "BLOCKED"
  | "IN_PROGRESS"
  | "PASS"
  | "FAIL"
  | "NOT_APPLICABLE";

export type ReadinessOverall =
  | "NOT_READY"
  | "CONDITIONALLY_READY"
  | "READY_FOR_CONTROLLED_PILOT";

export type RiskReviewStatus =
  | "UNREVIEWED"
  | "IN_REVIEW"
  | "ACCEPTED"
  | "REJECTED"
  | "NEEDS_INVESTIGATION"
  | "NEEDS_MORE_DATA";

export type CorrelationDecision =
  | "DUPLICATE"
  | "NOT_DUPLICATE"
  | "INSUFFICIENT_EVIDENCE";

export type InfrastructureValidationStatus =
  | "PENDING"
  | "VERIFIED"
  | "REJECTED"
  | "UNAVAILABLE";

export interface ReadinessCriterion {
  key: string;
  label: string;
  status: ReadinessStatus;
  blocking: boolean;
  evidence: string;
  evidence_refs: string[];
}

export interface ReadinessCategory {
  key: string;
  label: string;
  status: ReadinessStatus;
  mandatory: boolean;
  owner: string;
  summary: string;
  criteria: ReadinessCriterion[];
  blocking_issues: string[];
}

export interface PilotContextCheck {
  key: string;
  label: string;
  status: "PASS" | "FAIL";
  evidence: string;
}

export interface PilotContext {
  id: string;
  name: string;
  status: PilotStatus;
  mode: PilotMode;
  reviewers: number;
  checks: PilotContextCheck[];
  all_checks_pass: boolean;
}

export interface ReadinessReport {
  protocol: string;
  generated_at: string;
  overall: ReadinessOverall;
  ready_for_activation: boolean;
  activation_blockers: string[];
  categories: ReadinessCategory[];
  counts: Record<string, number>;
  mandatory_unmet: string[];
  advisory_unmet: string[];
  pilot_context: PilotContext | null;
  disclaimer: string;
  evidence_policy: string;
}

export interface PilotTransition {
  id: string;
  action: string;
  from_status: PilotStatus | null;
  to_status: PilotStatus;
  actor_id: string | null;
  actor_email: string | null;
  note: string | null;
  created_at: string;
}

export interface PilotReviewer {
  id: string;
  profile_id: string;
  role: string;
  full_name?: string | null;
}

export interface Pilot {
  id: string;
  pilot_key: string;
  name: string;
  description: string | null;
  status: PilotStatus;
  mode: PilotMode;
  region: string;
  bbox: number[];
  start_date: string;
  end_date: string;
  eligible_categories: string[];
  evaluation_protocol: string;
  operational_restrictions: string[];
  data_sources: string[];
  evaluation_criteria: string[];
  owner_id: string | null;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  activated_by: string | null;
  activated_at: string | null;
  paused_at: string | null;
  paused_by: string | null;
  pause_reason: string | null;
  completed_at: string | null;
  archived_at: string | null;
  rejection_reason: string | null;
  activation_readiness: Partial<ReadinessReport>;
  reviewers: PilotReviewer[];
  reviewer_count: number;
  history: PilotTransition[];
  allowed_actions: string[];
  created_at: string;
  updated_at: string;
  disclaimer: string;
}

export interface PilotList {
  items: Pilot[];
  total: number;
  limit: number;
  offset: number;
  disclaimer: string;
}

export interface RiskReviewEvent {
  id: string;
  from_status: RiskReviewStatus | null;
  to_status: RiskReviewStatus;
  actor_id: string | null;
  actor_email: string | null;
  note: string | null;
  requested_evidence: string | null;
  created_at: string;
}

export interface ReviewFactor {
  key?: string;
  label?: string;
  contribution?: number | null;
  available?: boolean;
  explanation?: string | null;
  [key: string]: unknown;
}

export interface RiskReviewCase {
  id: string;
  run_id: string;
  cell_id: string;
  pilot_id: string | null;
  pilot: {
    id: string;
    pilot_key: string;
    name: string;
    status: PilotStatus;
    mode: PilotMode;
  } | null;
  status: RiskReviewStatus;
  assigned_reviewer_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  last_decision_at: string | null;
  run: {
    id: string;
    model_version: string;
    config_hash: string;
    resolution: number;
    window_hours: number;
    window_start: string;
    window_end: string;
    calculated_at: string;
    incident_count: number;
    cell_count: number;
  } | null;
  risk: {
    id: string;
    h3_cell_id: string;
    risk_score: number | null;
    risk_category: string;
    confidence: number | null;
    factor_contributions: ReviewFactor[];
    available_factors: unknown;
    infrastructure_exposure: Record<string, unknown>;
    trend: Record<string, unknown>;
    calculated_at: string;
    model_version: string;
    config_hash: string;
  } | null;
  events: RiskReviewEvent[];
  review_disclaimer: string;
  prediction_vs_review: string;
}

export interface RiskReviewList {
  items: RiskReviewCase[];
  total: number;
  limit: number;
  offset: number;
  disclaimer: string;
}

export interface IncidentBrief {
  id: string;
  title: string | null;
  category: string | null;
  status: string | null;
  created_at: string | null;
}

export interface CorrelationReview {
  id: string;
  decision: CorrelationDecision;
  reviewer_id: string | null;
  reviewer_email: string | null;
  note: string | null;
  explanation: string | null;
  created_at: string;
}

export interface CorrelationCandidate {
  id: string;
  candidate_key: string;
  source_incident: IncidentBrief | null;
  target_incident: IncidentBrief | null;
  similarity_score: number | null;
  method: string;
  method_version: string;
  universe_key: string;
  universe_reference_complete: boolean;
  reference_universe_size: number | null;
  reference_note: string | null;
  synthetic_fixture: boolean | null;
  generated_at: string;
  created_by: string | null;
  review_state: "REVIEWED" | "UNREVIEWED";
  reviews: CorrelationReview[];
  disclaimer: string;
}

export interface CorrelationCandidateList {
  items: CorrelationCandidate[];
  total: number;
  limit: number;
  offset: number;
}

export interface CorrelationMetrics {
  protocol: string;
  universe_key: string;
  generated_at: string;
  evidence_kind: string;
  candidates: number;
  reviewed_candidates: number;
  unreviewed_candidates: number;
  labelled_candidates: number;
  abstained_candidates: number;
  contested_candidates: number;
  decision_counts: {
    duplicate: number;
    not_duplicate: number;
    insufficient_evidence: number;
  };
  metrics: {
    precision: number | null;
    recall: number | null;
    f1: number | null;
  };
  confusion_matrix: {
    true_positive: number;
    false_positive: number;
    false_negative: number | null;
    true_negative: number | null;
  };
  reviewer_agreement: {
    pairwise_agreement: number | null;
    compared_reviewer_pairs: number;
    reviewers: Record<string, number>;
    distinct_reviewers: number;
    multi_review_candidates: number;
  };
  reference: {
    complete: boolean;
    reference_universe_size: number | null;
    recall_reason: string;
  };
  limitations: string[];
  is_simulated: boolean | null;
  synthetic_provenance: "SYNTHETIC" | "OPERATIONAL" | "MIXED" | "UNKNOWN";
  is_validated_ground_truth: boolean;
}

export interface InfrastructureEvent {
  id: string;
  action: string;
  from_status: InfrastructureValidationStatus | null;
  to_status: InfrastructureValidationStatus;
  actor_email: string | null;
  note: string;
  created_at: string;
}

export interface InfrastructureSource {
  id: string;
  source_key: string;
  name: string;
  category: string;
  source_url: string;
  provider: string;
  license_note: string;
  retrieved_at: string;
  dataset_version: string;
  geographic_coverage: string;
  crs: string;
  schema_version: string;
  validation_status: InfrastructureValidationStatus;
  snapshot_sha256: string | null;
  update_frequency: string | null;
  known_limitations: string | null;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  events: InfrastructureEvent[];
  asset_data: null;
  asset_disclaimer: string;
}

export interface InfrastructureSourceList {
  items: InfrastructureSource[];
  total: number;
  limit: number;
  offset: number;
  disclaimer: string;
}

export interface InfrastructureCoverage {
  generated_at: string;
  domains: {
    category: string;
    label: string;
    state: "NO_SOURCE" | "UNVERIFIED" | "VERIFIED_METADATA";
    sources: number;
    verified: number;
  }[];
  verified_domains: number;
  total_domains: number;
  asset_data_available: false;
  disclaimer: string;
}

export interface SimulationCheck {
  key: string;
  label: string;
  status: "PASS" | "FAIL" | "UNKNOWN" | "NOT_APPLICABLE";
  evidence: string;
}

export interface SimulationAudit {
  protocol: string;
  generated_at: string;
  summary: {
    simulations: number;
    pass: number;
    fail: number;
    unknown: number;
    with_approved_review: number;
  };
  simulations: {
    id: string;
    simulation_label: "SIMULATED";
    scenario: {
      id: string;
      name: string | null;
      hazard_type: string | null;
      horizon_minutes: number | null;
      budget_limit: number | null;
    };
    strategy: string;
    status: string;
    validation_status: "PASS" | "FAIL" | "UNKNOWN";
    model_version: string;
    config_hash: string;
    calculated_at: string;
    duration_ms: number;
    objective: { score: number | null; components: Record<string, number> };
    plan_summary: {
      scheduled_actions: number;
      total_actions: number;
      resources_used: number;
      unknown_resources: number;
      metrics: Record<string, unknown>;
    };
    assumptions: string[];
    solver: Record<string, unknown>;
    warnings: string[];
    limitations: string[];
    human_reviews: {
      id: string;
      status: string;
      reviewed_by: string | null;
      created_at: string;
    }[];
    checks: SimulationCheck[];
    simulation_only: true;
    dispatch_permitted: false;
    resource_allocation_permitted: false;
    note: string;
  }[];
  limitations: string[];
  execution_authorized: false;
}

export interface TraceRunSummary {
  id: string;
  model_version: string;
  config_hash: string;
  resolution: number;
  window_hours: number;
  window_start: string;
  window_end: string;
  calculated_at: string;
  incident_count: number;
  cell_count: number;
  duration_ms: number;
  review_cases: number;
  reviewed_cases: number;
}

export interface RiskTrace {
  protocol: string;
  generated_at: string;
  exportable: boolean;
  read_only: boolean;
  assessment: {
    id: string;
    model_version: string;
    config_hash: string;
    resolution: number;
    window_hours: number;
    window_start: string;
    window_end: string;
    calculated_at: string;
    duration_ms: number;
    incident_count: number;
    cell_count: number;
    requested_by: string | null;
    query_parameters: Record<string, unknown>;
    summary: Record<string, unknown>;
    reproducible: boolean;
  };
  model_configuration: {
    found: boolean;
    model_name: string;
    version: string;
    config_hash_matches: boolean | null;
    config: Record<string, unknown> | null;
    description: string | null;
    registered_at: string | null;
    active_version: string | null;
    active_config_hash: string | null;
    active_matches_run: boolean;
    activation_changed: false;
    note: string;
  };
  inputs: {
    window_start: string;
    window_end: string;
    resolution: number;
    query_parameters: Record<string, unknown>;
    incident_count: number;
    cell_count: number;
    source_datasets: string[];
    source_lineage_complete: boolean;
  };
  spatial_units: {
    resolution: number;
    total_cells: number;
    returned_cells: number;
    truncated: boolean;
    cells: {
      id: string;
      h3_cell_id: string;
      risk_score: number | null;
      risk_category: string;
      confidence: number | null;
      calculated_at: string;
    }[];
  };
  factor_contributions: {
    key: string;
    label: string;
    available_share: number | null;
    mean_contribution: number | null;
    contribution_min: number | null;
    contribution_max: number | null;
    last_explanation: string | null;
  }[];
  reviews: {
    case_count: number;
    status_counts: Record<string, number>;
    reviewers: string[];
    cases: {
      id: string;
      cell_id: string;
      pilot_id: string | null;
      pilot: {
        id: string;
        name: string;
        status: PilotStatus;
        mode: PilotMode;
      } | null;
      status: RiskReviewStatus;
      assigned_reviewer_id: string | null;
      events: RiskReviewEvent[];
    }[];
    review_decision_distinct_from_prediction: true;
    note: string;
  };
  provenance: {
    complete: boolean;
    missing: string[];
    model_configuration_linked: boolean;
    dataset_lineage_linked: boolean;
    human_review_linked: boolean;
  };
  limitations: string[];
}
