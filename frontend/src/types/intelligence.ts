import type {
  IncidentCategory,
  IncidentSeverity,
  IncidentStatus,
  ProfileSummary,
} from "@/types/incidents";

export type RelationshipType = "RELATED" | "DUPLICATE" | "CONTEXT";
export type RelationshipStatus = "CONFIRMED" | "DISMISSED";

export type IncidentSummary = {
  id: string;
  title: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
};

export type IntelligenceSignal = {
  key: string;
  label: string;
  value: number | string | boolean | null;
  weight: number;
  contribution: number;
  explanation: string;
};

export type IncidentCandidate = {
  incident: IncidentSummary;
  distance_m: number;
  time_delta_seconds: number;
  text_similarity: number;
  confidence: number;
  reasons: string[];
  signals: IntelligenceSignal[];
};

export type IncidentRelationship = {
  id: string;
  incident_a_id: string;
  incident_b_id: string;
  other_incident: IncidentSummary;
  relationship_type: RelationshipType;
  status: RelationshipStatus;
  confidence: number;
  signals: Record<string, unknown>;
  note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AssetRef = {
  id: string;
  name: string;
  asset_type: string;
  criticality_score: number;
};

export type InfrastructureContext = {
  asset: AssetRef;
  distance_m: number;
  relationship: string;
  dependency_count: number;
};

export type ImpactPath = {
  root_asset: AssetRef;
  affected_asset: AssetRef;
  path: AssetRef[];
  depth: number;
  impact_type: "GEOSPATIAL_ASSOCIATION" | "INFERRED_POTENTIAL";
  confidence: number;
  rationale: string;
};

export type IncidentIntelligence = {
  incident_id: string;
  generated_at: string;
  duplicate_candidates: IncidentCandidate[];
  related_candidates: IncidentCandidate[];
  confirmed_relationships: IncidentRelationship[];
  infrastructure: InfrastructureContext[];
  potential_impacts: ImpactPath[];
  thresholds: Record<string, number>;
  limitations: string[];
};

export type InfrastructureAsset = {
  id: string;
  name: string;
  asset_type: string;
  location_wkt: string;
  description: string | null;
  criticality_score: number;
  is_active: boolean;
  metadata: Record<string, unknown>;
};

export type RelationshipReviewInput = {
  other_incident_id: string;
  relationship_type: RelationshipType;
  status: RelationshipStatus;
  confidence: number;
  signals?: Record<string, unknown>;
  note?: string | null;
};

export type RelationshipReviewer = ProfileSummary;
