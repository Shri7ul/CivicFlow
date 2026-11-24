export type EvidenceProvenance =
  | "REAL"
  | "SYNTHETIC"
  | "SIMULATED"
  | "MIXED"
  | "UNKNOWN";

export type ProvenanceKind =
  | "OPERATIONAL"
  | "SYNTHETIC"
  | "MIXED"
  | "UNKNOWN";

export type EvidenceQuality = "PASS" | "WARN" | "FAIL" | "UNKNOWN";
export type EvidenceVerification =
  | "PENDING"
  | "AUTOMATED_RECOMPUTATION"
  | "FAILED";

export interface EvidenceCheck {
  check: string;
  status: "PASS" | "WARN" | "FAIL";
  detail: string;
}

export interface EvidenceSnapshot {
  id: string;
  snapshot_key: string;
  kind: "RESEARCH_DATASET" | "INFRASTRUCTURE";
  status: "FETCHING" | "VALIDATED" | "FAILED" | "QUARANTINED" | "SUPERSEDED";
  source_key: string;
  source_url: string;
  provider: string;
  license_note: string;
  dataset_version: string;
  retrieved_at: string;
  snapshot_sha256: string | null;
  raw_sha256: string | null;
  schema_version: string;
  schema_fingerprint: string | null;
  record_count: number;
  raw_record_count: number;
  duplicate_count: number;
  invalid_count: number;
  missing_fields: number;
  byte_size: number;
  crs: string | null;
  bbox: number[];
  data_period_start: string | null;
  data_period_end: string | null;
  geographic_coverage: string | null;
  quality_status: EvidenceQuality;
  quality_checks: EvidenceCheck[];
  lineage: Record<string, unknown>;
  failure_reason: string | null;
  verification_status: EvidenceVerification;
  verification_checks: EvidenceCheck[];
  verification_note: string | null;
  verified_at: string | null;
  is_current: boolean;
  freshness_days: number | null;
  raw_available: boolean;
  normalized_available: boolean;
  validation_dataset_id: string | null;
  infrastructure_source_id: string | null;
  created_by: string | null;
  created_at: string;
  provenance: EvidenceProvenance;
  provenance_kind: ProvenanceKind;
  readiness: "REAL_ACQUIRED" | "NOT_OPERATIONAL_EVIDENCE";
  disclaimer: string;
  lineage_detail?: {
    normalization: string | null;
    coordinate_fallback_count: number | null;
    acquisition: string | null;
    raw_record_count: number;
    duplicate_history_rows: number;
  };
}

export interface DatasetRegistryEntry {
  dataset_key: string;
  name: string;
  region: string;
  period_start: string | null;
  period_end: string | null;
  record_count: number;
  status: string;
  schema_version: string;
  snapshot_sha256: string | null;
  source_url: string;
  license_note: string;
  freshness_days: number | null;
  provenance: EvidenceProvenance;
  provenance_kind: ProvenanceKind;
  evidence_snapshot: EvidenceSnapshot | null;
  quality: EvidenceQuality;
  verification: EvidenceVerification;
  external_role: string | null;
}

export interface GroundTruthRecord {
  id: string;
  record_key: string;
  incident_id: string | null;
  source_type: string;
  provenance_kind: ProvenanceKind;
  source_name: string;
  source_reference: string | null;
  incident_type: string;
  description: string | null;
  uncertainty: number | null;
  location: string | null;
  sensitive: boolean;
  status:
    | "UNVERIFIED"
    | "IN_REVIEW"
    | "VERIFIED"
    | "REJECTED"
    | "INSUFFICIENT_EVIDENCE";
  verification_method: string | null;
  verified_by: string | null;
  verified_at: string | null;
  evidence_refs: string[];
  verification_evidence_refs: string[];
  verification_note: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  disclaimer: string;
}

export interface GroundTruthSummary {
  total: number;
  status_counts: Record<string, number>;
  source_counts: Record<string, number>;
  provenance_counts: Record<string, number>;
  verified_count: number;
  operational_verified_count: number;
  human_verification: "NONE" | "PRESENT";
  recent: GroundTruthRecord[];
  workflow: string[];
}

export interface CorrelationUniverse {
  id: string;
  universe_key: string;
  name: string;
  description: string | null;
  version: string;
  provenance_kind: ProvenanceKind;
  reference_complete: boolean;
  reference_size: number | null;
  reference_note: string | null;
  candidate_method: string;
  candidate_method_version: string;
  reference_dataset_snapshot_id: string | null;
  attested_by: string | null;
  attested_at: string;
  immutable: boolean;
  disclaimer: string;
}

export interface CorrelationUniverseSummary extends CorrelationUniverse {
  candidate_count: number;
  reviewed_candidates: number;
  metrics: CorrelationMetrics | null;
}

export interface CorrelationMetrics {
  protocol: string;
  candidates: number;
  reviewed_candidates: number;
  unreviewed_candidates: number;
  decision_counts: Record<string, number>;
  metrics: {
    precision: number | null;
    recall: number | null;
    f1: number | null;
  };
  confusion_matrix: Record<string, number | null>;
  recall_reason: string;
  true_negatives: number | null;
  limitations: string[];
}

export interface InfrastructureSourceEntry {
  source_key: string;
  name: string;
  category: string;
  provider: string;
  source_url: string;
  license_note: string;
  dataset_version: string;
  retrieved_at: string;
  validation_status: string;
  integrated: boolean;
}

export interface InfrastructureDomain {
  domain: string;
  label: string;
  verified_source: boolean;
  integrated_snapshot: boolean;
}

export interface InfrastructureCoverageContext {
  status: "DESCRIPTIVE_ONLY" | "NOT_ASSESSED";
  dataset_key: string | null;
  bridge_assets: number;
  bridge_assets_with_coordinates: number;
  incidents: number;
  incidents_within_radius: number;
  radius_m: number;
  coverage: number | null;
  median_nearest_bridge_m: number | null;
  method: string;
  infra_aware_comparison: "NOT_ASSESSED";
  reason: string;
  caveat: string;
}

export interface ExternalResult {
  dataset_key: string;
  name: string;
  region: string;
  period_start: string | null;
  period_end: string | null;
  freshness_days: number | null;
  record_count: number;
  experiment_key: string;
  experiment_type: string;
  classification: "FRESH_EXTERNAL_HOLDOUT" | "HISTORICAL_OR_DIAGNOSTIC";
  evaluation_role: string | null;
  config_hash: string | null;
  civicflow: {
    pr_auc: number | null;
    roc_auc: number | null;
    precision_at_k: number | null;
    recall_at_k: number | null;
    fold_count: number | null;
  };
  baselines: Record<string, { pr_auc: number | null; roc_auc: number | null }>;
  strongest_baseline: string | null;
  beats_strongest_baseline: boolean | null;
  delta_pr_auc: number | null;
  confidence_interval: null;
  uncertainty_note: string;
  limitations: string[];
}

export interface EvidenceWorkspace {
  protocol: string;
  generated_at: string;
  evidence_integrity: {
    snapshots: number;
    current_snapshots: number;
    quality_counts: Record<string, number>;
    provenance_counts: Record<string, number>;
    automated_recomputations: number;
    quality_issues: {
      snapshot_key: string;
      check: string;
      status: string;
      detail: string;
    }[];
    real_data_disclaimer: string;
  };
  dataset_registry: DatasetRegistryEntry[];
  snapshots: EvidenceSnapshot[];
  ground_truth: GroundTruthSummary;
  correlation: {
    universes: CorrelationUniverseSummary[];
    candidate_total: number;
    reviewed_candidate_total: number;
    recall_available: boolean;
    true_negatives_available: boolean;
    note: string;
  };
  infrastructure: {
    domains: InfrastructureDomain[];
    domains_integrated: number;
    domains_verified: number;
    sources: InfrastructureSourceEntry[];
    assets_total: number;
    assets_by_type: Record<string, number>;
    independent_automated_checks: number;
    coverage_context: InfrastructureCoverageContext | null;
  };
  external_validation: {
    results: ExternalResult[];
    registered_fresh_datasets: number;
    methodology: string;
    baseline_note: string;
  };
  blockers: string[];
  not_assessed: string[];
  synthetic_separation: string;
}

export interface EvidenceSnapshotList {
  items: EvidenceSnapshot[];
  total: number;
  limit: number;
  offset: number;
  disclaimer: string;
}
