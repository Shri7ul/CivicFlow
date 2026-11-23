"""Central model registry.

Importing this module registers every mapped class with ``Base.metadata`` for
Alembic and application use. Keep all new models listed here.
"""

from app.models.audit import RoleChangeAudit
from app.models.base import Base
from app.models.cluster import IncidentCluster, IncidentClusterMember
from app.models.department import Department
from app.models.enums import (
    AssetType,
    ClusterStatus,
    DependencyType,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RiskEntityType,
    RiskLevel,
    Role,
    ScenarioStatus,
)
from app.models.incident import Incident, IncidentEvidence, IncidentStatusEvent
from app.models.infrastructure import DependencyEdge, InfrastructureAsset
from app.models.profile import Profile
from app.models.risk import RiskAssessment, RiskCell
from app.models.scenario import Scenario, ScenarioResult

__all__ = [
    "AssetType",
    "Base",
    "ClusterStatus",
    "DependencyEdge",
    "DependencyType",
    "Department",
    "Incident",
    "IncidentCategory",
    "IncidentCluster",
    "IncidentClusterMember",
    "IncidentEvidence",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentStatusEvent",
    "InfrastructureAsset",
    "Profile",
    "RiskAssessment",
    "RiskCell",
    "RiskEntityType",
    "RiskLevel",
    "Role",
    "RoleChangeAudit",
    "Scenario",
    "ScenarioResult",
    "ScenarioStatus",
]
