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
