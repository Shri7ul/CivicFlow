"""Enumerations shared by the CivicFlow database schema."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    CITIZEN = "CITIZEN"
    WORKER = "WORKER"
    ADMIN = "ADMIN"


class IncidentCategory(str, Enum):
    ROADS = "ROADS"
    DRAINAGE = "DRAINAGE"
    SANITATION = "SANITATION"
    UTILITIES = "UTILITIES"
    PUBLIC_SAFETY = "PUBLIC_SAFETY"
    HEALTH = "HEALTH"
    ENVIRONMENT = "ENVIRONMENT"
    OTHER = "OTHER"


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ClusterStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


class RelationshipType(str, Enum):
    RELATED = "RELATED"
    DUPLICATE = "DUPLICATE"
    CONTEXT = "CONTEXT"


class RelationshipStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class AssetType(str, Enum):
    ROAD = "ROAD"
    DRAIN = "DRAIN"
    HOSPITAL = "HOSPITAL"
    SCHOOL = "SCHOOL"
    SHELTER = "SHELTER"
    FIRE_STATION = "FIRE_STATION"
    WATER_FACILITY = "WATER_FACILITY"
    POWER_FACILITY = "POWER_FACILITY"
    OTHER = "OTHER"


class DependencyType(str, Enum):
    CONNECTS_TO = "CONNECTS_TO"
    FEEDS = "FEEDS"
    SERVES = "SERVES"
    DEPENDS_ON = "DEPENDS_ON"
    ADJACENT_TO = "ADJACENT_TO"
    PROTECTS = "PROTECTS"
    OTHER = "OTHER"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


class RiskCategory(str, Enum):
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TrendDirection(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RiskEntityType(str, Enum):
    INCIDENT = "INCIDENT"
    INFRASTRUCTURE_ASSET = "INFRASTRUCTURE_ASSET"
    DEPARTMENT = "DEPARTMENT"
    RISK_CELL = "RISK_CELL"
    SCENARIO = "SCENARIO"


class ScenarioStatus(str, Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ScenarioHazard(str, Enum):
    FLOOD = "FLOOD"
    DRAINAGE = "DRAINAGE"
    ROAD = "ROAD"
    FIRE = "FIRE"
    HEALTH = "HEALTH"
    UTILITY = "UTILITY"
    MULTI_HAZARD = "MULTI_HAZARD"
    OTHER = "OTHER"


class ResponseActionType(str, Enum):
    INSPECT = "INSPECT"
    DISPATCH = "DISPATCH"
    REPAIR = "REPAIR"
    CLEAN = "CLEAN"
    EVACUATE = "EVACUATE"
    SHELTER = "SHELTER"
    MEDICAL = "MEDICAL"
    UTILITY = "UTILITY"
    COMMUNICATION = "COMMUNICATION"
    OTHER = "OTHER"


class ResourceType(str, Enum):
    PERSONNEL = "PERSONNEL"
    VEHICLE = "VEHICLE"
    EQUIPMENT = "EQUIPMENT"
    SUPPLY = "SUPPLY"
    FACILITY = "FACILITY"
    OTHER = "OTHER"


class ResourceAvailability(str, Enum):
    UNKNOWN = "UNKNOWN"
    AVAILABLE = "AVAILABLE"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    PLANNING_ASSUMPTION = "PLANNING_ASSUMPTION"


class ResourceAllocationMode(str, Enum):
    SHARED_CAPACITY = "SHARED_CAPACITY"
    CONSUMABLE = "CONSUMABLE"


class DecisionStrategy(str, Enum):
    PRIORITY = "PRIORITY"
    RISK_REDUCTION = "RISK_REDUCTION"
    COST_EFFICIENT = "COST_EFFICIENT"
    BALANCED = "BALANCED"


class SimulationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ModelLifecycleAction(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVATED = "ACTIVATED"
    DEACTIVATED = "DEACTIVATED"


class EvaluationMethod(str, Enum):
    HISTORICAL_BACKTEST = "HISTORICAL_BACKTEST"
    TIME_SPLIT = "TIME_SPLIT"
    SPATIAL = "SPATIAL"
    CALIBRATION = "CALIBRATION"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class EvaluationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class SourceReliability(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    VERIFIED = "VERIFIED"
    COMMUNITY = "COMMUNITY"
    UNVERIFIED = "UNVERIFIED"
    PLANNING_ASSUMPTION = "PLANNING_ASSUMPTION"


class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    UNAVAILABLE = "UNAVAILABLE"


class IngestionStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DataQualityStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class AlertRuleType(str, Enum):
    RISK_THRESHOLD = "RISK_THRESHOLD"
    DATA_FRESHNESS = "DATA_FRESHNESS"
    INGESTION_FAILURE = "INGESTION_FAILURE"
    SYSTEM = "SYSTEM"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"


class NotificationDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class DecisionReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    SUPERSEDED = "SUPERSEDED"


class ValidationDatasetStatus(str, Enum):
    REGISTERED = "REGISTERED"
    VALIDATED = "VALIDATED"
    INSUFFICIENT = "INSUFFICIENT"


class ValidationEvidenceKind(str, Enum):
    EMPIRICAL_OBSERVATIONAL = "EMPIRICAL_OBSERVATIONAL"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    SIMULATED_PLANNING = "SIMULATED_PLANNING"


class ValidationExperimentType(str, Enum):
    RISK_BACKTEST = "RISK_BACKTEST"
    RISK_SENSITIVITY = "RISK_SENSITIVITY"
    CORRELATION_SYNTHETIC = "CORRELATION_SYNTHETIC"
    DECISION_SIMULATION = "DECISION_SIMULATION"


class ValidationStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"
