export type DecisionStrategy =
  | "PRIORITY"
  | "RISK_REDUCTION"
  | "COST_EFFICIENT"
  | "BALANCED";

export type ScenarioHazard =
  | "FLOOD"
  | "DRAINAGE"
  | "ROAD"
  | "FIRE"
  | "HEALTH"
  | "UTILITY"
  | "MULTI_HAZARD"
  | "OTHER";

export type ScenarioStatus =
  | "DRAFT"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "ARCHIVED";

export type ResponseActionType =
  | "INSPECT"
  | "DISPATCH"
  | "REPAIR"
  | "CLEAN"
  | "EVACUATE"
  | "SHELTER"
  | "MEDICAL"
  | "UTILITY"
  | "COMMUNICATION"
  | "OTHER";

export type ResourceType =
  | "PERSONNEL"
  | "VEHICLE"
  | "EQUIPMENT"
  | "SUPPLY"
  | "FACILITY"
  | "OTHER";

export type ResourceAvailability =
  | "UNKNOWN"
  | "AVAILABLE"
  | "LIMITED"
  | "UNAVAILABLE"
  | "PLANNING_ASSUMPTION";

export type ResourceAllocationMode = "SHARED_CAPACITY" | "CONSUMABLE";

export interface DecisionConfig {
  model_version: string;
  config_hash: string;
  horizon_minutes: { min: number; max: number };
  max_actions: number;
  max_resources: number;
  solver_time_limit_ms: number;
  default_risk_window_hours: number;
  default_resolution: number;
  objective_weights: Record<string, number>;
  strategies: { value: DecisionStrategy; label: string }[];
  limitations: string[];
}

export interface ResponseResource {
  id: string;
  name: string;
  resource_type: ResourceType;
  unit: string;
  quantity_available: number;
  availability_status: ResourceAvailability;
  availability_source: string | null;
  available_as_of: string | null;
  allocation_mode: ResourceAllocationMode;
  department_id: string | null;
  is_active: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ResourceRequirement {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  unit: string;
  quantity_required: number;
  availability_status: ResourceAvailability;
}

export interface DecisionAction {
  id: string;
  scenario_id: string;
  title: string;
  description: string | null;
  action_type: ResponseActionType;
  target_h3_cell_id: string | null;
  target_asset_id: string | null;
  target_asset_name: string | null;
  department_id: string | null;
  department_name: string | null;
  priority: number;
  earliest_start_minutes: number;
  duration_minutes: number;
  expected_risk_reduction: number;
  estimated_cost: number | null;
  depends_on_action_id: string | null;
  is_active: boolean;
  assumptions: Record<string, unknown>;
  resource_requirements: ResourceRequirement[];
  created_at: string;
  updated_at: string;
}

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string | null;
  hazard_type: ScenarioHazard;
  status: ScenarioStatus;
  horizon_minutes: number;
  budget_limit: number | null;
  resolution: number;
  risk_window_hours: number;
  parameters: Record<string, unknown>;
  action_count: number;
  simulation_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioDetail extends ScenarioSummary {
  actions: DecisionAction[];
}

export interface ScenarioCreateInput {
  name: string;
  description?: string | null;
  hazard_type: ScenarioHazard;
  horizon_minutes?: number;
  budget_limit?: number | null;
  resolution?: number;
  risk_window_hours?: number;
  parameters?: Record<string, unknown>;
}

export interface ActionCreateInput {
  title: string;
  description?: string | null;
  action_type: ResponseActionType;
  target_h3_cell_id?: string | null;
  target_asset_id?: string | null;
  department_id?: string | null;
  priority?: number;
  earliest_start_minutes?: number;
  duration_minutes?: number;
  expected_risk_reduction?: number;
  estimated_cost?: number | null;
  depends_on_action_id?: string | null;
  assumptions?: Record<string, unknown>;
  resource_requirements?: { resource_id: string; quantity_required: number }[];
}

export interface ResourceCreateInput {
  name: string;
  resource_type: ResourceType;
  unit: string;
  quantity_available?: number;
  availability_status?: ResourceAvailability;
  availability_source?: string | null;
  available_as_of?: string | null;
  allocation_mode?: ResourceAllocationMode;
  department_id?: string | null;
  is_active?: boolean;
  metadata?: Record<string, unknown>;
}

export interface PlanAction {
  action_id: string;
  title: string;
  description: string | null;
  action_type: ResponseActionType;
  priority: number;
  status: "SCHEDULED" | "BLOCKED" | "DEFERRED" | "UNSCHEDULED";
  start_minute: number | null;
  end_minute: number | null;
  duration_minutes: number;
  expected_risk_reduction: number;
  planned_reduction: number;
  target_h3_cell_id: string | null;
  target_risk_score: number | null;
  target_asset_id: string | null;
  target_asset_name: string | null;
  department_id: string | null;
  department_name: string | null;
  depends_on_action_id: string | null;
  estimated_cost: number | null;
  reasons: string[];
  resources: Record<string, unknown>[];
  assumptions: Record<string, unknown>;
}

export interface PlanResource {
  resource_id: string;
  name: string;
  resource_type: ResourceType;
  unit: string;
  capacity: number;
  used: number;
  remaining: number;
  availability_status: ResourceAvailability;
  allocation_mode: ResourceAllocationMode;
  availability_source: string | null;
  available_as_of: string | null;
  planned_only: boolean;
}

export interface PlanMetrics {
  total_actions: number;
  scheduled_actions: number;
  blocked_actions: number;
  deferred_actions: number;
  action_coverage: number;
  priority_coverage: number;
  planned_reduction: number;
  max_possible_reduction: number;
  reduction_rate: number;
  total_known_cost: number;
  budget_limit: number | null;
  makespan_minutes: number;
  horizon_minutes: number;
  time_efficiency: number;
  cost_efficiency: number;
  unknown_cost_actions: number;
  objective_score: number;
}

export interface SimulationPlan {
  strategy: DecisionStrategy;
  strategy_label: string;
  objective_score: number;
  objective_components: Record<string, number>;
  metrics: PlanMetrics;
  actions: PlanAction[];
  resources: PlanResource[];
  solver: Record<string, unknown>;
  assumptions: string[];
  warnings: string[];
  limitations: string[];
  execution_authorized: false;
  dispatch_performed: false;
  reservations_created: false;
  rank?: number;
}

export interface RiskContextSummary {
  available: boolean;
  resolution: number;
  window_hours: number;
  cell_count: number;
  incident_count: number;
  cells: Record<string, number>;
  limitations: string[];
}

export interface SimulationResponse {
  simulation_id: string | null;
  scenario_id: string;
  scenario_name: string;
  strategy: DecisionStrategy;
  status: "COMPLETED" | "PARTIAL" | "FAILED";
  model_version: string;
  config_hash: string;
  risk_context: RiskContextSummary;
  plan: SimulationPlan;
  assumptions: string[];
  warnings: string[];
  limitations: string[];
  execution_authorized: false;
  dispatch_performed: false;
  reservations_created: false;
  generated_at: string;
  calculated_at: string | null;
}

export interface ComparisonResponse {
  scenario_id: string;
  scenario_name: string;
  model_version: string;
  config_hash: string;
  risk_context: RiskContextSummary;
  comparison: {
    winner: DecisionStrategy | null;
    results: SimulationPlan[];
    solver: Record<string, unknown>;
    assumptions: string[];
    warnings: string[];
    limitations: string[];
    execution_authorized: false;
    dispatch_performed: false;
    reservations_created: false;
  };
  generated_at: string;
}

export interface SimulationListItem {
  id: string;
  scenario_id: string;
  strategy: DecisionStrategy;
  status: "COMPLETED" | "PARTIAL" | "FAILED";
  model_version: string;
  config_hash: string;
  duration_ms: number;
  calculated_at: string;
  summary: Record<string, unknown>;
}
