export type RiskCategory =
  | "MINIMAL"
  | "LOW"
  | "MODERATE"
  | "HIGH"
  | "CRITICAL";

export type RiskFactor = {
  key: string;
  label: string;
  raw_value: number | string | boolean | null;
  normalized: number | null;
  weight: number;
  contribution: number;
  available: boolean;
  explanation: string;
};

export type RiskTrend = {
  available: boolean;
  direction: "INCREASING" | "DECREASING" | "STABLE" | "INSUFFICIENT_DATA";
  direction_label: string;
  delta_score: number;
  current_score: number;
  previous_score: number;
  current_incident_count: number;
  previous_incident_count: number;
  reason: string;
};

export type RiskAssetExposure = {
  id: string;
  name: string;
  asset_type: string;
  criticality_score: number;
  distance_m: number;
  dependency_count: number;
  source: string | null;
};

export type RiskInfrastructure = {
  available: boolean;
  nearby_asset_count: number;
  by_type: Record<string, number>;
  dependency_count: number;
  normalized_exposure: number | null;
  assets: RiskAssetExposure[];
  dataset: Record<string, unknown>;
  explanation: string;
};

export type RiskCell = {
  h3_cell_id: string;
  resolution: number;
  boundary: GeoJSONPolygon;
  center_latitude: number;
  center_longitude: number;
  risk_score: number;
  incident_activity_score: number;
  risk_category: RiskCategory;
  confidence: number;
  confidence_label: string;
  incident_count: number;
  active_count: number;
  adjusted_incident_count: number;
  removed_duplicates: number;
  severity_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  factors: RiskFactor[];
  infrastructure: RiskInfrastructure;
  trend: RiskTrend;
  calculated_at: string;
  model_version: string;
  config_hash: string;
};

export type GeoJSONPolygon = {
  type: "Polygon";
  coordinates: number[][][];
};

export type RiskIncidentBrief = {
  id: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  created_at: string;
};

export type RiskCellDetail = RiskCell & {
  incidents: RiskIncidentBrief[];
  limitations: string[];
};

export type RiskCellBrief = {
  h3_cell_id: string;
  resolution: number;
  center_latitude: number;
  center_longitude: number;
  risk_score: number;
  risk_category: RiskCategory;
  confidence: number;
  confidence_label: string;
  incident_count: number;
  active_count: number;
  trend_direction: RiskTrend["direction"];
};

export type RiskDataset = {
  active_asset_count: number;
  authoritative_asset_count: number;
  development_or_unknown_asset_count: number;
  asset_limit_reached: boolean;
  is_authoritative: boolean;
};

export type RiskSummary = {
  total_cells: number;
  current_incident_count: number;
  adjusted_incident_count: number;
  duplicate_adjusted_count: number;
  category_distribution: Record<string, number>;
  high_critical_cells: number;
  increasing_cells: number;
  decreasing_cells: number;
  stable_cells: number;
  insufficient_trend_cells: number;
  mean_risk_score: number;
  max_risk_score: number;
  mean_incident_activity_score: number;
  mean_confidence: number;
  exposure_cells: number;
  exposure_asset_count: number;
  factor_means: Record<string, number>;
  top_cells: RiskCellBrief[];
  dataset: RiskDataset;
  history_coverage: number;
};

export type RiskCellsResponse = {
  items: RiskCell[];
  total: number;
  offset: number;
  limit: number;
  resolution: number;
  window_hours: number;
  window_start: string;
  window_end: string;
  generated_at: string;
  model_version: string;
  config_hash: string;
  history_coverage: number;
  dataset: RiskDataset;
  privacy: Record<string, unknown>;
  summary: RiskSummary;
  limitations: string[];
};

export type RiskGeoJSON = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    id: string;
    geometry: GeoJSONPolygon;
    properties: {
      h3_cell_id: string;
      resolution: number;
      risk_score: number;
      incident_activity_score: number;
      risk_category: RiskCategory;
      confidence: number;
      confidence_label: string;
      incident_count: number;
      active_count: number;
      trend_direction: RiskTrend["direction"];
      nearby_asset_count: number;
    };
  }>;
  model_version: string;
  config_hash: string;
  generated_at: string;
  window_hours: number;
  resolution: number;
  privacy: Record<string, unknown>;
  limitations: string[];
};

export type RiskBand = {
  category: RiskCategory;
  label: string;
  color: string;
  min_score: number;
  max_score: number;
};

export type RiskConfig = {
  model_version: string;
  config_hash: string;
  factor_weights: Record<string, number>;
  factor_labels: Record<string, string>;
  severity_weights: Record<string, number>;
  category_weights: Record<string, number>;
  bands: RiskBand[];
  resolutions: { min: number; default: number; max: number };
  windows: { default_hours: number; max_hours: number };
  recency_half_life_hours: number;
  density_saturation: number;
  infrastructure_radius_m: number;
  max_incidents: number;
  max_cells: number;
  privacy_min_incidents: number;
  trend_min_incidents: number;
  limitations: string[];
};

export type RiskTrendCell = {
  h3_cell_id: string;
  resolution: number;
  boundary: GeoJSONPolygon;
  center_latitude: number;
  center_longitude: number;
  current_score: number;
  previous_score: number;
  delta_score: number;
  direction: RiskTrend["direction"];
  direction_label: string;
  current_incident_count: number;
  previous_incident_count: number;
  current_category: RiskCategory;
  confidence: number;
  reason: string;
};

export type RiskTrendsResponse = {
  items: RiskTrendCell[];
  counts: Record<string, number>;
  resolution: number;
  window_hours: number;
  window_start: string;
  window_end: string;
  generated_at: string;
  model_version: string;
  config_hash: string;
  privacy: Record<string, unknown>;
  limitations: string[];
};

export type RiskInfrastructureSummary = {
  total_cells: number;
  exposed_cells: number;
  cells_with_authoritative_dataset: number;
  by_asset_type: Record<string, number>;
  top_assets: Array<Record<string, unknown>>;
  dataset: RiskDataset;
  limitations: string[];
};

export type RiskFilters = {
  resolution?: number;
  window?: "current" | "24h" | "7d" | "30d";
  minScore?: number;
  category?: RiskCategory | "";
  minLatitude?: number;
  minLongitude?: number;
  maxLatitude?: number;
  maxLongitude?: number;
  limit?: number;
  offset?: number;
};
