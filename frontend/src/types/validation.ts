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
export type ResearchRole = "development" | "external";

export type ResearchMetric = {
  pr_auc: number | null;
  roc_auc: number | null;
  precision_at_k: number | null;
  recall_at_k: number | null;
  fold_count: number | null;
};

export type ResearchInterval = {
  n: number;
  mean: number | null;
  ci_low: number | null;
  ci_high: number | null;
  resamples?: number;
  seed?: number;
  note?: string;
};

export type ResearchPairedComparison = {
  n: number;
  mean_delta: number | null;
  median_delta?: number | null;
  ci_low: number | null;
  ci_high: number | null;
  wins: number | null;
  losses: number | null;
  ties?: number | null;
  sign_test_p: number | null;
  bootstrap_probability_positive?: number | null;
  note?: string;
};

export type ResearchBaselineRow = ResearchMetric & {
  method: string;
  delta_pr_auc: number | null;
  ci_low: number | null;
  ci_high: number | null;
  wins: number | null;
  losses: number | null;
  sign_test_p: number | null;
};

export type ResearchFactorDiagnostic = {
  availability_rate: number;
  available_count: number;
  observations: number;
  zero_share: number;
  mean_normalized: number | null;
  target_spearman: number | null;
  mean_when_target_active: number | null;
  mean_when_target_inactive: number | null;
};

export type ResearchHypothesis = {
  severity: "high" | "medium" | "low" | string;
  finding: string;
  evidence: string;
};

export type ResearchRedundancyPair = {
  factors?: string[];
  spearman?: number | null;
  [key: string]: unknown;
};

export type ResearchBandDistribution = Record<
  string,
  { count: number; share: number }
>;

export type ResearchDiagnostics = {
  hypotheses: ResearchHypothesis[];
  factor_diagnostics: Record<string, ResearchFactorDiagnostic>;
  factor_redundancy: ResearchRedundancyPair[];
  band_distribution: ResearchBandDistribution;
  score_distribution: Record<string, unknown>;
  data_quality: Record<string, unknown>;
  baseline_comparison: Record<string, unknown>;
  limitations: string[];
};

export type ResearchAblationVariant = {
  variant_key: string;
  kind: string;
  removed_factors: string[];
  only_factors: string[];
  pr_auc: number | null;
  roc_auc: number | null;
  precision_at_k: number | null;
  recall_at_k: number | null;
  mean_delta: number | null;
  ci_low: number | null;
  ci_high: number | null;
  wins: number | null;
  losses: number | null;
  sign_test_p: number | null;
};

export type ResearchAblation = {
  status: string | null;
  variants: ResearchAblationVariant[];
  ranking: {
    variant_key: string;
    pr_auc: number | null;
    roc_auc: number | null;
    precision_at_k: number | null;
    recall_at_k: number | null;
  }[];
  best_variant: string | null;
  best_minus_full_pr_auc: number | null;
  interpretation: string | null;
  limitations: string[];
};

export type ResearchRobustnessRow = {
  resolution?: number;
  target_hours?: number;
  retained_fraction?: number;
  retained_records?: number | null;
  cell_count?: number | null;
  pr_auc: number | null;
  roc_auc: number | null;
  precision_at_k: number | null;
  recall_at_k: number | null;
  mean_spearman: number | null;
  mean_top20_jaccard: number | null;
};

export type ResearchDensityStratum = ResearchMetric & {
  mean_positive_cells?: number;
  status?: string;
  note?: string;
};

export type ResearchThresholdVariant = {
  cell_total: number;
  thresholds: Record<string, number>;
  cell_counts: Record<string, number>;
};

export type ResearchRobustness = {
  status: string | null;
  base_metrics: ResearchMetric;
  resolution: ResearchRobustnessRow[];
  target_window: ResearchRobustnessRow[];
  record_thinning: ResearchRobustnessRow[];
  density_strata: {
    note?: string;
    dense?: ResearchDensityStratum;
    sparse?: ResearchDensityStratum;
  };
  threshold_sensitivity: {
    origin?: string;
    note?: string;
    variants: Record<string, ResearchThresholdVariant>;
  };
  missingness: Record<string, number | string>;
  runtime_ms?: number;
  limitations: string[];
};

export type ResearchCandidate = {
  experiment_id: string;
  variant_key: string;
  sample: "selection" | "external_holdout";
  candidate_key: string;
  removed_factors: string[];
  metrics: ResearchMetric & { completed_folds?: number };
  reference_metrics: ResearchMetric & { completed_folds?: number };
  delta_pr_auc: ResearchPairedComparison;
  delta_roc_auc: ResearchPairedComparison;
  activated: boolean;
  limitations: string[];
};

export type ResearchStatistics = {
  method?: string;
  config_hash?: string;
  evaluation_unit?: string;
  fold_intervals: Record<string, ResearchInterval>;
  paired_pr_auc_vs_baselines: Record<string, ResearchPairedComparison>;
};

export type ResearchDatasetSummary = {
  dataset_id: string;
  dataset_key: string;
  name: string;
  region: string;
  period_start: string | null;
  period_end: string | null;
  record_count: number;
  snapshot_sha256: string;
  schema_version: string;
  status: string;
  evidence_kind: ValidationEvidenceKind;
  model_version: string | null;
  config_hash: string | null;
  split_method: string | null;
  role: ResearchRole;
  risk: ResearchMetric;
  baselines: ResearchBaselineRow[];
  best_baseline: ResearchBaselineRow | null;
  statistics: ResearchStatistics;
  density: {
    classification?: string;
    mean_label_prevalence?: number;
    mean_universe_cells?: number;
    mean_target_cells?: number;
    mean_target_records?: number;
    note?: string;
  };
  sensitivity: Record<string, unknown>;
  diagnostics: ResearchDiagnostics;
  ablation: ResearchAblation;
  candidates: ResearchCandidate[];
  robustness: ResearchRobustness;
  findings: string[];
  limitations: string[];
  experiments: Record<
    string,
    { id: string; name: string; status: string; completed_at: string | null }
  >;
};

export type ResearchSelection = {
  candidate_key: string | null;
  selection_dataset: string;
  rule: string;
  reason: string;
  selection_statistics: ResearchPairedComparison | null;
  removed_factors: string[];
  weights: Record<string, number>;
};

export type Phase9Summary = {
  protocol_key: string;
  protocol: string;
  split_method: string;
  development_dataset: string;
  dataset_count: number;
  mean_pr_auc_across_datasets: number | null;
  evidence_kind: ValidationEvidenceKind;
  evidence_policy: string[];
  selection: ResearchSelection;
  datasets: ResearchDatasetSummary[];
};

export type ResearchComparisonRow = {
  dataset_key: string;
  role: ResearchRole;
  region: string;
  period_start: string | null;
  period_end: string | null;
  record_count: number;
  civicflow_pr_auc: number | null;
  civicflow_roc_auc: number | null;
  best_baseline: string | null;
  best_baseline_pr_auc: number | null;
  pr_auc_delta_vs_best_baseline: number | null;
  density_classification: string | null;
  factor_count: number;
};

export type ResearchModelChanges = {
  activated: boolean;
  activation_state: string;
  active_model_version: string | null;
  active_config_hash: string | null;
  selection_rule: string | null;
  selected_candidate: string | null;
  selection_dataset: string | null;
  selection_reason: string | null;
  candidate_rows: (ResearchCandidate & { dataset_key?: string })[];
  decision: string;
  governance_note: string;
};

export type Phase9Report = {
  protocol_key: string;
  generated_at: string;
  source: string;
  evidence_kind: ValidationEvidenceKind;
  executive_summary: string[];
  phase8_findings: Record<string, unknown> | null;
  diagnostic_audit: {
    dataset_key: string;
    role: ResearchRole;
    hypotheses: ResearchHypothesis[];
    factor_diagnostics: Record<string, ResearchFactorDiagnostic>;
    factor_redundancy: ResearchRedundancyPair[];
    band_distribution: ResearchBandDistribution;
    score_distribution: Record<string, unknown>;
  }[];
  datasets: {
    dataset_key: string;
    name: string;
    region: string;
    period_start: string | null;
    period_end: string | null;
    record_count: number;
    snapshot_sha256: string;
    schema_version: string;
    role: ResearchRole;
    source_url: string | null;
    license_note: string | null;
    bbox: number[] | null;
    evidence_kind: ValidationEvidenceKind;
  }[];
  dataset_quality: {
    dataset_key: string;
    data_quality: Record<string, unknown>;
    density: ResearchDatasetSummary["density"] | null;
    missingness: Record<string, number | string>;
  }[];
  methodology: Record<string, unknown>;
  split_methodology: Record<string, unknown>;
  baselines: { dataset_key: string; rows: ResearchBaselineRow[] }[];
  ablation: (ResearchAblation & { dataset_key: string })[];
  geographic: ResearchComparisonRow[];
  temporal: {
    dataset_key: string;
    period_start: string | null;
    period_end: string | null;
    pr_auc: number | null;
    roc_auc: number | null;
    density: string | null;
    fold_count: number | null;
  }[];
  sensitivity: {
    dataset_key: string;
    resolution: ResearchRobustnessRow[];
    target_window: ResearchRobustnessRow[];
    record_thinning: ResearchRobustnessRow[];
    density_strata: ResearchRobustness["density_strata"];
    threshold_sensitivity: ResearchRobustness["threshold_sensitivity"];
    missingness: Record<string, number | string>;
  }[];
  statistics: {
    dataset_key: string;
    fold_intervals: Record<string, ResearchInterval>;
    paired_pr_auc_vs_baselines: Record<string, ResearchPairedComparison>;
    method: string | null;
  }[];
  model_changes: ResearchModelChanges;
  comparison: ResearchComparisonRow[];
  limitations: string[];
  reproducibility: Record<string, unknown>;
  future_research: string[];
  dataset_count: number;
};
