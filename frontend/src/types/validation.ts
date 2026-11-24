export type ValidationDatasetStatus = "REGISTERED" | "VALIDATED" | "INSUFFICIENT";

export type ValidationEvidenceKind =
  | "EMPIRICAL_OBSERVATIONAL"
  | "SYNTHETIC_FIXTURE"
  | "SIMULATED_PLANNING";

export type ValidationDataset = {
  id: string;
  dataset_key: string;
  name: string;
  description: string | null;
  source_url: string;
  license_note: string;
  region: string;
  period_start: string | null;
  period_end: string | null;
  source_id: string | null;
  ingestion_run_id: string | null;
  snapshot_sha256: string;
  snapshot_path: string | null;
  record_count: number;
  schema_version: string;
  status: ValidationDatasetStatus;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ValidationExperiment = {
  id: string;
  experiment_key: string;
  name: string;
  experiment_type: string;
  evidence_kind: ValidationEvidenceKind;
  status: "RUNNING" | "COMPLETED" | "INSUFFICIENT_DATA" | "FAILED";
  dataset_id: string | null;
  method: string;
  split_method: string | null;
  record_count: number;
  model_name: string | null;
  model_version: string | null;
  config_hash: string | null;
  findings: string[];
  limitations: string[];
  started_at: string;
  completed_at: string | null;
};

export type ValidationExperimentDetail = ValidationExperiment & {
  dataset_version: string | null;
  dataset_snapshot_sha256: string | null;
  region: string | null;
  period_start: string | null;
  period_end: string | null;
  metrics: Record<string, unknown>;
  baselines: Record<string, unknown>;
  reproducibility: Record<string, unknown>;
  error_summary: string | null;
};

export type ValidationOverview = {
  datasets: ValidationDataset[];
  experiments: ValidationExperiment[];
  evidence_kinds: ValidationEvidenceKind[];
  limitations: string[];
};

export type ValidationReport = {
  experiment_id: string;
  experiment_key: string;
  name: string;
  status: string;
  experiment_type: string;
  evidence_kind: ValidationEvidenceKind;
  executive_summary: string;
  dataset: {
    key: string;
    name: string;
    source_url: string;
    license_note: string;
    region: string;
    period_start: string | null;
    period_end: string | null;
    snapshot_sha256: string;
    record_count: number;
    schema_version: string;
    metadata: Record<string, unknown>;
  } | null;
  methodology: {
    method: string;
    split_method: string | null;
    model_name: string | null;
    model_version: string | null;
    config_hash: string | null;
  };
  dataset_snapshot_sha256: string | null;
  metrics: Record<string, unknown>;
  baselines: Record<string, unknown>;
  findings: string[];
  limitations: string[];
  reproducibility: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
};
