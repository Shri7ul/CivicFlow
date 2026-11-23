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
    RelationshipStatus,
    RelationshipType,
    RiskCategory,
    RiskEntityType,
    RiskLevel,
    Role,
    ScenarioStatus,
    TrendDirection,
)
from app.models.incident import Incident, IncidentEvidence, IncidentStatusEvent
from app.models.infrastructure import DependencyEdge, InfrastructureAsset
from app.models.intelligence import IncidentRelationship
from app.models.profile import Profile
from app.models.risk import (
    RiskAssessment,
    RiskCell,
    RiskCellSnapshot,
    RiskModelRun,
)
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
    "IncidentRelationship",
    "InfrastructureAsset",
    "Profile",
    "RiskAssessment",
    "RiskCategory",
    "RiskCell",
    "RiskCellSnapshot",
    "RiskEntityType",
    "RiskModelRun",
    "RelationshipStatus",
    "RelationshipType",
    "RiskLevel",
    "Role",
    "RoleChangeAudit",
    "Scenario",
    "ScenarioResult",
    "ScenarioStatus",
    "TrendDirection",
]
