export type ModelRecord = {
  id: string;
  model_name: "risk" | "decision";
  version: string;
  config_hash: string;
  description: string | null;
  is_active: boolean;
  activated_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type EvaluationRecord = {
  id: string;
  model_version_id: string;
  method: string;
  status: string;
  dataset_label: string;
  is_synthetic: boolean;
  ground_truth_available: boolean;
  split_strategy: string;
  sample_count: number;
  metrics: Record<string, number | null>;
  slices: Record<string, unknown>;
  warnings: string[];
  created_at: string;
};

export type DataSourceRecord = {
  id: string;
  source_key: string;
  name: string;
  category: string;
  access_method: string;
  license_note: string | null;
  reliability: string;
  status: string;
  adapter: string;
  freshness_target_minutes: number;
  retry_limit: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type QualityRecord = {
  id: string;
  source_id: string;
  status: string;
  freshness_minutes: number | null;
  records_total: number;
  invalid_records: number;
  duplicate_records: number;
  missing_fields: number;
  issues: string[];
  coverage: Record<string, unknown>;
  recorded_at: string;
};

export type QualityItem = {
  source: DataSourceRecord;
  status: string;
  freshness_minutes: number | null;
  issues: string[];
  snapshot: QualityRecord | null;
};

export type AlertRecord = {
  id: string;
  rule_id: string | null;
  severity: string;
  status: string;
  title: string;
  message: string;
  dedupe_key: string;
  context: Record<string, unknown>;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
};

export type NotificationRecord = {
  id: string;
  alert_id: string;
  channel: string;
  delivery_status: string;
  dedupe_key: string;
  created_at: string;
  delivered_at: string | null;
  read_at: string | null;
};

export type ReviewRecord = {
  id: string;
  scenario_id: string;
  simulation_id: string | null;
  title: string;
  status: string;
  submitted_by: string | null;
  submitted_by_name: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  decision_note: string | null;
  created_at: string;
  updated_at: string;
  execution_authorized: boolean;
  dispatch_performed: boolean;
  reservations_created: boolean;
};

export type Dashboard = {
  generated_at: string;
  incidents: { by_status: Record<string, number>; last_24h: number };
  risk: {
    available: boolean;
    resolution: number;
    window_hours: number;
    cell_count: number;
    max_score: number | null;
    bands: Record<string, number>;
    incident_count: number;
  };
  data_quality: {
    sources: Array<{
      source_id: string;
      source_key: string;
      name: string;
      reliability: string;
      status: string;
      freshness_minutes: number | null;
      issues: string[];
      last_run: string | null;
    }>;
    warnings: string[];
    stale_or_unknown: number;
  };
  models: {
    items: ModelRecord[];
    active_risk: { id: string; version: string; config_hash: string } | null;
    active_decision: { id: string; version: string; config_hash: string } | null;
    latest_evaluation: EvaluationRecord | null;
  };
  alerts: {
    active_by_severity: Record<string, number>;
    recent: AlertRecord[];
  };
  planning: {
    scenario_count: number;
    simulation_count: number;
    pending_review_count: number;
    pending_reviews: ReviewRecord[];
  };
  health: { database: boolean; app_env: string };
  safety: {
    dispatch_performed: boolean;
    execution_authorized: boolean;
    reservations_created: boolean;
    note: string;
  };
};

export type SourceCreateInput = {
  source_key: string;
  name: string;
  category: string;
  access_method: string;
  license_note?: string | null;
  reliability: string;
  status?: string;
  adapter?: string;
  freshness_target_minutes?: number;
  retry_limit?: number;
  required_fields?: string[];
  metadata?: Record<string, unknown>;
};

export type AlertRuleCreateInput = {
  name: string;
  rule_type: string;
  metric: string;
  operator?: string;
  threshold_value?: number | null;
  severity: string;
  cooldown_minutes?: number;
  dedupe_window_minutes?: number;
};

export type ReviewDecision = "APPROVED" | "REJECTED" | "REVISION_REQUESTED";
