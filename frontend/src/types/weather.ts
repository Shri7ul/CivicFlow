export type WeatherAssessmentStatus = "OK" | "STALE" | "ERROR" | "DISABLED";

export type WeatherRelevance = "LIKELY" | "POSSIBLE";

export interface WeatherCurrent {
  observed_at: string | null;
  temperature_c: number | null;
  precipitation_mm: number | null;
  wind_speed_kmh: number | null;
  wind_gusts_kmh: number | null;
  weather_code: number | null;
}

export interface WeatherForecastHour {
  time: string;
  temperature_c: number | null;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
}

export interface WeatherSnapshot {
  provider: string;
  latitude: number;
  longitude: number;
  retrieved_at: string;
  data_quality: string;
  current: WeatherCurrent;
  forecast: WeatherForecastHour[];
}

export interface WeatherSignal {
  rule_id: string;
  kind: "AGGRAVATION" | "SECONDARY_HAZARD" | "CONTEXT";
  relevance: WeatherRelevance;
  explanation: string;
  evidence: Record<string, unknown>;
}

export interface WeatherAssessmentOutput {
  status: string;
  rule_engine_version: string;
  category: string;
  context_tags: string[];
  weather_summary: {
    current: WeatherCurrent;
    forecast_hours: number;
    forecast_from: string | null;
    forecast_to: string | null;
    data_quality: string;
  };
  signals: WeatherSignal[];
  potential_aggravation: string[];
  potential_secondary_hazards: string[];
  context_notes: string[];
  uncertainty: string;
  decision_note: string;
  rule_ids: string[];
  stale_reason?: string;
  refresh_reason?: string;
  explanation?: string;
  error_code?: string;
}

export interface WeatherAssessment {
  id: string;
  incident_id: string;
  status: WeatherAssessmentStatus;
  provider: string;
  retrieved_at: string;
  observed_at: string | null;
  forecast_from: string | null;
  forecast_to: string | null;
  weather_snapshot: WeatherSnapshot;
  assessment: WeatherAssessmentOutput;
  rule_engine_version: string;
  error_code: string | null;
  refresh_count: number;
  last_attempt_at: string | null;
  stale: boolean;
  source_attribution: string;
  created_at: string;
  updated_at: string;
}

export interface WeatherConfig {
  enabled: boolean;
  provider: string;
  rule_engine_version: string;
  cache_ttl_minutes: number;
  forecast_hours: number;
  api_key_configured: boolean;
  source_attribution: string;
}
