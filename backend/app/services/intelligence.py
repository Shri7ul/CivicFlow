"""Explainable incident correlation, duplicate detection, and impact context.

The engine is deliberately deterministic and human-reviewable. It computes
suggestions from existing incident records and infrastructure/dependency data;
it never merges, mutates, or deletes incidents. Workers and admins persist only
their review decisions.
"""

from __future__ import annotations

import difflib
import math
import re
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models import (
    DependencyEdge,
    Incident,
    IncidentCategory,
    IncidentRelationship,
    IncidentSeverity,
    IncidentStatus,
    InfrastructureAsset,
    RelationshipStatus,
    RelationshipType,
    Role,
)
from app.schemas.intelligence import (
    AssetRef,
    ImpactPath,
    IncidentCandidate,
    IncidentIntelligenceResponse,
    IncidentSummary,
    InfrastructureContext,
    IntelligenceSignal,
    RelationshipResponse,
)
from app.services.incidents import get_incident, is_staff, parse_point, point_wkt

SIGNAL_WEIGHTS: dict[str, float] = {
    "distance": 0.32,
    "time": 0.18,
    "text": 0.23,
    "category": 0.13,
    "severity": 0.04,
    "status": 0.10,
}

_RELATED_CATEGORIES: dict[IncidentCategory, frozenset[IncidentCategory]] = {
    IncidentCategory.ROADS: frozenset(
        {IncidentCategory.DRAINAGE, IncidentCategory.PUBLIC_SAFETY}
    ),
    IncidentCategory.DRAINAGE: frozenset(
        {
            IncidentCategory.ROADS,
            IncidentCategory.SANITATION,
            IncidentCategory.HEALTH,
        }
    ),
    IncidentCategory.SANITATION: frozenset(
        {IncidentCategory.DRAINAGE, IncidentCategory.HEALTH}
    ),
    IncidentCategory.UTILITIES: frozenset(
        {IncidentCategory.PUBLIC_SAFETY, IncidentCategory.ENVIRONMENT}
    ),
    IncidentCategory.PUBLIC_SAFETY: frozenset(
        {
            IncidentCategory.ROADS,
            IncidentCategory.UTILITIES,
            IncidentCategory.HEALTH,
        }
    ),
    IncidentCategory.HEALTH: frozenset(
        {
            IncidentCategory.DRAINAGE,
            IncidentCategory.SANITATION,
            IncidentCategory.PUBLIC_SAFETY,
        }
    ),
    IncidentCategory.ENVIRONMENT: frozenset(
        {
            IncidentCategory.DRAINAGE,
            IncidentCategory.SANITATION,
            IncidentCategory.UTILITIES,
        }
    ),
    IncidentCategory.OTHER: frozenset(),
}

_STOPWORDS = {
    "the",
    "and",
    "for",
    "this",
    "that",
    "with",
    "from",
    "have",
    "near",
    "after",
    "before",
    "there",
    "where",
    "which",
    "into",
    "over",
    "under",
    "road",
    "street",
}

_SEVERITY_RANK = {
    IncidentSeverity.LOW: 0,
    IncidentSeverity.MEDIUM: 1,
    IncidentSeverity.HIGH: 2,
    IncidentSeverity.CRITICAL: 3,
}
_WKT_RE = re.compile(r"^\s*(POINT|LINESTRING|POLYGON)\s*\((.*)\)\s*$", re.I)


@dataclass(frozen=True)
class ScoredCandidate:
    incident: Incident
    distance_m: float
    time_delta_seconds: int
    text_similarity: float
    category_similarity: float
    confidence: float
    reasons: tuple[str, ...]
    signals: tuple[IntelligenceSignal, ...]
    is_duplicate: bool


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    radius = 6_371_008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _normalise_text(value: str) -> str:
    return " ".join(
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in _STOPWORDS
    )


def _tokens(value: str) -> set[str]:
    return set(_normalise_text(value).split())


def text_similarity(first: str, second: str) -> float:
    """Blend token overlap and sequence similarity for explainable matching."""
    first_text = _normalise_text(first)
    second_text = _normalise_text(second)
    if not first_text or not second_text:
        return 0.0
    first_tokens = set(first_text.split())
    second_tokens = set(second_text.split())
    union = first_tokens | second_tokens
    jaccard = len(first_tokens & second_tokens) / len(union) if union else 0.0
    sequence = difflib.SequenceMatcher(None, first_text, second_text).ratio()
    return round(0.65 * jaccard + 0.35 * sequence, 6)


def category_similarity(
    first: IncidentCategory, second: IncidentCategory
) -> float:
    if first is second:
        return 1.0
    if second in _RELATED_CATEGORIES.get(first, frozenset()):
        return 0.55
    return 0.0


def _severity_similarity(
    first: IncidentSeverity, second: IncidentSeverity
) -> float:
    return 1.0 - abs(_SEVERITY_RANK[first] - _SEVERITY_RANK[second]) / 3.0


def _status_similarity(
    first: IncidentStatus, second: IncidentStatus
) -> float:
    if first is second:
        return 1.0
    open_states = {
        IncidentStatus.OPEN,
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.IN_PROGRESS,
    }
    if first in open_states and second in open_states:
        return 0.8
    if first in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED} and second in {
        IncidentStatus.RESOLVED,
        IncidentStatus.CLOSED,
    }:
        return 0.7
    return 0.25


def _distance_component(distance_m: float, radius_m: float) -> float:
    if radius_m <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance_m / radius_m))


def _time_component(seconds: int, window_seconds: int) -> float:
    if window_seconds <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - seconds / window_seconds))


def _wkt_vertices(value: str) -> tuple[str, list[tuple[float, float]]]:
    match = _WKT_RE.match(value or "")
    if not match:
        raise ValueError("Unsupported infrastructure geometry")
    geometry_type = match.group(1).upper()
    body = match.group(2).strip()
    if geometry_type == "POLYGON":
        # Distance to the exterior ring is sufficient for foundation context.
        body = body.strip("()").split("),", 1)[0].strip("()")
    pairs: list[tuple[float, float]] = []
    for pair in body.split(","):
        parts = pair.strip().strip("()").split()
        if len(parts) < 2:
            continue
        pairs.append((float(parts[0]), float(parts[1])))
    if not pairs:
        raise ValueError("Infrastructure geometry has no coordinates")
    return geometry_type, pairs


def _segment_distance(
    latitude: float,
    longitude: float,
    first: tuple[float, float],
    second: tuple[float, float],
    origin_latitude: float,
    origin_longitude: float,
) -> float:
    """Point-to-segment distance in metres using a local equirectangular frame."""
    cos_lat = math.cos(math.radians(origin_latitude))
    ax = (first[0] - origin_longitude) * 111_320 * cos_lat
    ay = (first[1] - origin_latitude) * 110_540
    bx = (second[0] - origin_longitude) * 111_320 * cos_lat
    by = (second[1] - origin_latitude) * 110_540
    px, py = 0.0, 0.0
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def geometry_distance_m(
    latitude: float,
    longitude: float,
    geometry_wkt: str,
) -> float:
    """Portable distance used for SQLite tests and non-PostGIS fallback."""
    geometry_type, vertices = _wkt_vertices(geometry_wkt)
    if geometry_type == "POINT" or len(vertices) == 1:
        vertex = vertices[0]
        return haversine_m(latitude, longitude, vertex[1], vertex[0])
    distances = [
        _segment_distance(
            latitude,
            longitude,
            vertices[index],
            vertices[index + 1],
            latitude,
            longitude,
        )
        for index in range(len(vertices) - 1)
    ]
    if geometry_type == "POLYGON" and len(vertices) > 1:
        distances.append(
            _segment_distance(
                latitude,
                longitude,
                vertices[-1],
                vertices[0],
                latitude,
                longitude,
            )
        )
    return min(distances) if distances else math.inf


def _origin_point(incident: Incident) -> tuple[float, float]:
    return parse_point(incident.location)


def _visible_candidate_query(user: AuthenticatedUser):
    statement = select(Incident)
    if not is_staff(user):
        statement = statement.where(Incident.reporter_id == user.profile.id)
    return statement


def _nearby_incidents(
    session: Session,
    *,
    origin: Incident,
    user: AuthenticatedUser,
    radius_m: float,
    window_hours: int,
    limit: int,
) -> list[Incident]:
    """Use PostGIS for bounded candidate retrieval; compute scores in Python."""
    latitude, longitude = _origin_point(origin)
    created_at = _utc(origin.created_at)
    statement = _visible_candidate_query(user).where(
        Incident.id != origin.id,
        Incident.created_at >= created_at - timedelta(hours=window_hours),
        Incident.created_at <= created_at + timedelta(hours=window_hours),
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.where(
            func.ST_DWithin(
                Incident.location,
                func.ST_GeogFromText(point_wkt(latitude, longitude)),
                radius_m,
            )
        )
    statement = statement.order_by(Incident.created_at.desc()).limit(limit)
    candidates = list(session.scalars(statement).all())
    nearby: list[Incident] = []
    for candidate in candidates:
        candidate_latitude, candidate_longitude = _origin_point(candidate)
        distance = haversine_m(
            latitude,
            longitude,
            candidate_latitude,
            candidate_longitude,
        )
        if distance <= radius_m:
            nearby.append(candidate)
    return nearby


def _score_candidate(
    origin: Incident,
    candidate: Incident,
    *,
    distance_m: float,
    settings: Settings,
) -> ScoredCandidate:
    delta_seconds = abs(
        int(
            (
                _utc(candidate.created_at) - _utc(origin.created_at)
            ).total_seconds()
        )
    )
    text_score = text_similarity(
        f"{candidate.title} {candidate.description}",
        f"{origin.title} {origin.description}",
    )
    category_score = category_similarity(origin.category, candidate.category)
    severity_score = _severity_similarity(origin.severity, candidate.severity)
    status_score = _status_similarity(origin.status, candidate.status)
    distance_score = _distance_component(
        distance_m, settings.intelligence_duplicate_radius_m
    )
    # Time is scored against the duplicate window; the wider related window is
    # handled by candidate retrieval and the final confidence threshold.
    time_score = _time_component(
        delta_seconds, settings.intelligence_duplicate_window_hours * 3600
    )

    components = {
        "distance": distance_score,
        "time": time_score,
        "text": text_score,
        "category": category_score,
        "severity": severity_score,
        "status": status_score,
    }
    confidence = round(
        sum(SIGNAL_WEIGHTS[key] * value for key, value in components.items()),
        3,
    )

    signal_explanations = {
        "distance": (
            f"{distance_m:.0f} m apart; duplicate radius is "
            f"{settings.intelligence_duplicate_radius_m} m"
        ),
        "time": (
            f"{delta_seconds // 60} min apart; duplicate window is "
            f"{settings.intelligence_duplicate_window_hours} h"
        ),
        "text": (
            f"Text similarity is {text_score:.0%} using normalised token "
            "overlap (65%) and sequence similarity (35%)"
        ),
        "category": (
            "Same category"
            if category_score == 1.0
            else "Related category"
            if category_score > 0
            else "Different category"
        ),
        "severity": (
            f"Severity differs by "
            f"{abs(_SEVERITY_RANK[origin.severity] - _SEVERITY_RANK[candidate.severity])} level(s)"
        ),
        "status": (
            "Same lifecycle status"
            if status_score == 1.0
            else "Both incidents are active"
            if status_score >= 0.8
            else "Lifecycle status differs"
        ),
    }
    signals = tuple(
        IntelligenceSignal(
            key=key,
            label={
                "distance": "Spatial proximity",
                "time": "Temporal proximity",
                "text": "Description similarity",
                "category": "Category compatibility",
                "severity": "Severity similarity",
                "status": "Lifecycle status compatibility",
            }[key],
            value=(
                round(components[key], 3)
                if key not in {"distance"}
                else round(distance_m, 1)
            ),
            weight=SIGNAL_WEIGHTS[key],
            contribution=round(SIGNAL_WEIGHTS[key] * components[key], 3),
            explanation=signal_explanations[key],
        )
        for key in SIGNAL_WEIGHTS
    )

    reasons: list[str] = []
    if distance_m <= settings.intelligence_duplicate_radius_m:
        reasons.append(f"Within {distance_m:.0f} m of the report")
    if delta_seconds <= settings.intelligence_duplicate_window_hours * 3600:
        reasons.append(f"Reported within {delta_seconds // 60} minutes")
    if category_score == 1.0:
        reasons.append("Same incident category")
    elif category_score > 0:
        reasons.append("Potentially related incident category")
    if text_score >= settings.intelligence_duplicate_text_threshold:
        reasons.append(f"Description similarity {text_score:.0%}")
    if status_score >= 0.8:
        reasons.append("Both reports are active")

    is_duplicate = (
        distance_m <= settings.intelligence_duplicate_radius_m
        and delta_seconds <= settings.intelligence_duplicate_window_hours * 3600
        and category_score > 0
        and text_score >= settings.intelligence_duplicate_text_threshold
        and confidence >= settings.intelligence_duplicate_confidence_threshold
    )
    return ScoredCandidate(
        incident=candidate,
        distance_m=round(distance_m, 2),
        time_delta_seconds=delta_seconds,
        text_similarity=round(text_score, 3),
        category_similarity=round(category_score, 3),
        confidence=confidence,
        reasons=tuple(reasons),
        signals=signals,
        is_duplicate=is_duplicate,
    )


def _candidate_response(candidate: ScoredCandidate) -> IncidentCandidate:
    incident = candidate.incident
    return IncidentCandidate(
        incident=IncidentSummary(
            id=incident.id,
            title=incident.title,
            category=incident.category,
            severity=incident.severity,
            status=incident.status,
        ),
        distance_m=candidate.distance_m,
        time_delta_seconds=candidate.time_delta_seconds,
        text_similarity=candidate.text_similarity,
        confidence=candidate.confidence,
        reasons=list(candidate.reasons),
        signals=list(candidate.signals),
    )


def _asset_ref(asset: InfrastructureAsset) -> AssetRef:
    return AssetRef(
        id=asset.id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        criticality_score=float(asset.criticality_score),
    )


def _asset_distances(
    session: Session,
    *,
    latitude: float,
    longitude: float,
    radius_m: int,
) -> list[tuple[InfrastructureAsset, float]]:
    """Return nearby active assets, bounded by a PostGIS spatial predicate.

    ``location`` is a WGS84 geometry with a GIST index, so the bounding
    predicate uses ``ST_DWithin`` on geometry before an accurate geography
    distance is computed for display and scoring.
    """
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        point_geometry = func.ST_SetSRID(
            func.ST_MakePoint(longitude, latitude), 4326
        )
        # The indexed column is geometry in EPSG:4326, so ST_DWithin's scalar
        # radius is in degrees. Use a conservative per-axis bound derived from
        # the local latitude, then compute the authoritative distance below
        # with geography (metres). This avoids false negatives while still
        # letting the GIST index narrow the candidate set.
        longitude_metres_per_degree = 111_320 * max(
            math.cos(math.radians(latitude)), 0.01
        )
        degree_radius = max(
            radius_m / 110_540,
            radius_m / longitude_metres_per_degree,
        )
        distance_expr = func.ST_Distance(
            func.ST_GeogFromText(
                func.ST_AsText(InfrastructureAsset.location)
            ),
            func.ST_GeogFromText(point_wkt(latitude, longitude)),
        )
        rows = session.execute(
            select(InfrastructureAsset, distance_expr.label("distance_m"))
            .where(
                InfrastructureAsset.is_active.is_(True),
                func.ST_DWithin(
                    InfrastructureAsset.location,
                    point_geometry,
                    degree_radius,
                ),
            )
            .order_by(distance_expr)
            .limit(50)
        ).all()
        return [(asset, float(distance)) for asset, distance in rows]
    assets = session.scalars(
        select(InfrastructureAsset).where(
            InfrastructureAsset.is_active.is_(True)
        )
    ).all()
    return [
        (asset, geometry_distance_m(latitude, longitude, asset.location))
        for asset in assets
    ]


def _impact_paths(
    contexts: list[InfrastructureContext],
    assets_by_id: dict[uuid.UUID, InfrastructureAsset],
    edges: list[DependencyEdge],
    *,
    max_depth: int,
    limit: int,
    radius_m: int,
) -> list[ImpactPath]:
    outgoing: dict[uuid.UUID, list[DependencyEdge]] = {}
    incoming: dict[uuid.UUID, list[DependencyEdge]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source_asset_id, []).append(edge)
        incoming.setdefault(edge.target_asset_id, []).append(edge)

    impacts: list[ImpactPath] = []
    for context in contexts:
        root = assets_by_id.get(context.asset.id)
        if root is None:
            continue
        root_confidence = round(
            max(
                0.30,
                min(
                    0.90,
                    0.55
                    + (1.0 - context.distance_m / radius_m) * 0.20
                    + float(root.criticality_score) / 100.0,
                ),
            ),
            3,
        )
        root_ref = context.asset
        impacts.append(
            ImpactPath(
                root_asset=root_ref,
                affected_asset=root_ref,
                path=[root_ref],
                depth=0,
                impact_type="GEOSPATIAL_ASSOCIATION",
                confidence=root_confidence,
                rationale=(
                    f"{root.name} is {context.distance_m:.0f} m from the "
                    "incident location. This is a spatial association, not "
                    "evidence of damage."
                ),
            )
        )
        queue: deque[
            tuple[InfrastructureAsset, int, list[AssetRef], float, str]
        ] = deque([(root, 0, [root_ref], root_confidence, "")])
        visited = {root.id}
        while queue and len(impacts) < limit:
            asset, depth, path, confidence, _ = queue.popleft()
            if depth >= max_depth:
                continue
            related_edges: list[tuple[DependencyEdge, bool]] = [
                (edge, False) for edge in outgoing.get(asset.id, [])
            ] + [
                (edge, True) for edge in incoming.get(asset.id, [])
            ]
            for edge, incoming_edge in related_edges:
                neighbor_id = (
                    edge.source_asset_id if incoming_edge else edge.target_asset_id
                )
                if neighbor_id in visited:
                    continue
                neighbor = assets_by_id.get(neighbor_id)
                if neighbor is None:
                    continue
                visited.add(neighbor_id)
                edge_confidence = float(edge.strength)
                next_confidence = round(
                    max(0.05, min(0.90, confidence * edge_confidence * 0.85)),
                    3,
                )
                next_path = [*path, _asset_ref(neighbor)]
                direction = "incoming" if incoming_edge else "outgoing"
                rationale = (
                    f"{edge.dependency_type.value.replace('_', ' ').title()} "
                    f"edge ({direction}, strength {edge_confidence:.2f}) links "
                    f"{asset.name} to {neighbor.name}. This is an inferred "
                    "dependency association, not an observed impact."
                )
                impacts.append(
                    ImpactPath(
                        root_asset=root_ref,
                        affected_asset=_asset_ref(neighbor),
                        path=next_path,
                        depth=depth + 1,
                        impact_type="INFERRED_POTENTIAL",
                        confidence=next_confidence,
                        rationale=rationale,
                    )
                )
                queue.append(
                    (
                        neighbor,
                        depth + 1,
                        next_path,
                        next_confidence,
                        rationale,
                    )
                )
                if len(impacts) >= limit:
                    break
    return impacts[:limit]


def _infrastructure_context(
    session: Session,
    *,
    latitude: float,
    longitude: float,
    settings: Settings,
) -> tuple[list[InfrastructureContext], list[ImpactPath]]:
    rows = _asset_distances(
        session,
        latitude=latitude,
        longitude=longitude,
        radius_m=settings.intelligence_infrastructure_radius_m,
    )
    contexts: list[InfrastructureContext] = []
    included_assets: dict[uuid.UUID, InfrastructureAsset] = {}
    for asset, distance in rows:
        if distance > settings.intelligence_infrastructure_radius_m:
            continue
        if len(contexts) >= 10:
            break
        included_assets[asset.id] = asset
        contexts.append(
            InfrastructureContext(
                asset=_asset_ref(asset),
                distance_m=round(distance, 1),
                relationship="NEARBY",
                dependency_count=0,
            )
        )

    if not contexts:
        return [], []

    edges = list(session.scalars(select(DependencyEdge)).all())
    counts = Counter()
    for edge in edges:
        counts[edge.source_asset_id] += 1
        counts[edge.target_asset_id] += 1
    contexts = [
        context.model_copy(
            update={"dependency_count": counts.get(context.asset.id, 0)}
        )
        for context in contexts
    ]
    all_assets = session.scalars(select(InfrastructureAsset)).all()
    assets_by_id = {asset.id: asset for asset in all_assets}
    impacts = _impact_paths(
        contexts,
        assets_by_id,
        edges,
        max_depth=settings.intelligence_impact_depth,
        limit=settings.intelligence_impact_limit,
        radius_m=settings.intelligence_infrastructure_radius_m,
    )
    return contexts, impacts


def _relationship_response(
    relationship: IncidentRelationship,
    *,
    origin_id: uuid.UUID,
) -> RelationshipResponse:
    other = (
        relationship.incident_b
        if relationship.incident_a_id == origin_id
        else relationship.incident_a
    )
    return RelationshipResponse(
        id=relationship.id,
        incident_a_id=relationship.incident_a_id,
        incident_b_id=relationship.incident_b_id,
        other_incident=IncidentSummary(
            id=other.id,
            title=other.title,
            category=other.category,
            severity=other.severity,
            status=other.status,
        ),
        relationship_type=relationship.relationship_type,
        status=relationship.status,
        confidence=float(relationship.confidence),
        signals=relationship.signals or {},
        note=relationship.note,
        reviewed_by=relationship.reviewed_by,
        reviewed_at=relationship.reviewed_at,
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
    )


def list_relationships(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
) -> list[RelationshipResponse]:
    get_incident(session, incident_id, user)
    relationships = session.scalars(
        select(IncidentRelationship)
        .where(
            or_(
                IncidentRelationship.incident_a_id == incident_id,
                IncidentRelationship.incident_b_id == incident_id,
            )
        )
        .order_by(IncidentRelationship.updated_at.desc())
    ).all()
    visible: list[RelationshipResponse] = []
    for relationship in relationships:
        other_id = (
            relationship.incident_b_id
            if relationship.incident_a_id == incident_id
            else relationship.incident_a_id
        )
        other = session.get(Incident, other_id)
        if other is None:
            continue
        if not is_staff(user) and other.reporter_id != user.profile.id:
            # Do not reveal another Citizen's incident through a relationship.
            continue
        visible.append(
            _relationship_response(relationship, origin_id=incident_id)
        )
    return visible


def review_relationship(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    other_incident_id: uuid.UUID,
    relationship_type: RelationshipType,
    status: RelationshipStatus,
    confidence: float,
    signals: dict,
    note: str | None,
) -> RelationshipResponse:
    if user.profile.role not in (Role.WORKER, Role.ADMIN):
        raise AppError(
            "Only workers and administrators can review relationships.",
            status_code=403,
            code="insufficient_role",
        )
    if incident_id == other_incident_id:
        raise AppError(
            "An incident cannot be related to itself.",
            status_code=422,
            code="self_relationship",
        )
    get_incident(session, incident_id, user)
    other = session.get(Incident, other_incident_id)
    if other is None:
        raise AppError(
            "Incident not found.",
            status_code=404,
            code="incident_not_found",
        )

    a_id, b_id = sorted((incident_id, other_incident_id), key=str)
    relationship = session.scalar(
        select(IncidentRelationship).where(
            IncidentRelationship.incident_a_id == a_id,
            IncidentRelationship.incident_b_id == b_id,
            IncidentRelationship.relationship_type == relationship_type,
        )
    )
    now = datetime.now(timezone.utc)
    if relationship is None:
        relationship = IncidentRelationship(
            incident_a_id=a_id,
            incident_b_id=b_id,
            relationship_type=relationship_type,
            status=status,
            confidence=confidence,
            signals=signals,
            note=note,
            reviewed_by=user.profile.id,
            reviewed_at=now,
        )
        session.add(relationship)
    else:
        relationship.status = status
        relationship.confidence = confidence
        relationship.signals = signals
        relationship.note = note
        relationship.reviewed_by = user.profile.id
        relationship.reviewed_at = now
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "The relationship was changed by another review. Retry the review.",
            status_code=409,
            code="relationship_conflict",
        ) from exc
    except Exception:
        session.rollback()
        raise
    session.refresh(relationship)
    return _relationship_response(relationship, origin_id=incident_id)


def build_intelligence(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    settings: Settings | None = None,
) -> IncidentIntelligenceResponse:
    settings = settings or get_settings()
    origin = get_incident(session, incident_id, user)
    latitude, longitude = _origin_point(origin)
    candidates = _nearby_incidents(
        session,
        origin=origin,
        user=user,
        radius_m=settings.intelligence_related_radius_m,
        window_hours=settings.intelligence_related_window_hours,
        limit=settings.intelligence_candidate_limit,
    )
    # Compute distance once per candidate and keep the scoring inputs explicit.
    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        candidate_latitude, candidate_longitude = _origin_point(candidate)
        distance = haversine_m(
            latitude,
            longitude,
            candidate_latitude,
            candidate_longitude,
        )
        scored.append(
            _score_candidate(
                origin,
                candidate,
                distance_m=distance,
                settings=settings,
            )
        )

    duplicates = sorted(
        [candidate for candidate in scored if candidate.is_duplicate],
        key=lambda candidate: candidate.confidence,
        reverse=True,
    )
    duplicate_ids = {candidate.incident.id for candidate in duplicates}
    related = sorted(
        [
            candidate
            for candidate in scored
            if candidate.incident.id not in duplicate_ids
            and candidate.confidence
            >= settings.intelligence_related_confidence_threshold
        ],
        key=lambda candidate: candidate.confidence,
        reverse=True,
    )

    contexts, impacts = _infrastructure_context(
        session,
        latitude=latitude,
        longitude=longitude,
        settings=settings,
    )
    limitations = [
        "Correlation suggestions are explainable heuristics, not confirmed "
        "facts. Incidents are never merged automatically.",
        "Infrastructure proximity establishes geospatial association only; it "
        "does not establish damage, outage, or service disruption.",
        "Dependency paths are inferred graph associations and are not a "
        "real-world cascading-impact prediction.",
    ]
    if not contexts:
        limitations.append(
            "No active infrastructure assets are within the configured radius; "
            "the repository does not ship an external municipal asset feed."
        )
    else:
        limitations.append(
            "Infrastructure records currently come from the repository's "
            "development seed unless a deployment has loaded an authoritative "
            "municipal dataset."
        )

    return IncidentIntelligenceResponse(
        incident_id=origin.id,
        generated_at=datetime.now(timezone.utc),
        duplicate_candidates=[_candidate_response(item) for item in duplicates],
        related_candidates=[_candidate_response(item) for item in related],
        confirmed_relationships=list_relationships(
            session, user=user, incident_id=incident_id
        ),
        infrastructure=contexts,
        potential_impacts=impacts,
        thresholds={
            "duplicate_radius_m": settings.intelligence_duplicate_radius_m,
            "related_radius_m": settings.intelligence_related_radius_m,
            "duplicate_window_hours": (
                settings.intelligence_duplicate_window_hours
            ),
            "related_window_hours": settings.intelligence_related_window_hours,
            "duplicate_text_threshold": (
                settings.intelligence_duplicate_text_threshold
            ),
            "duplicate_confidence_threshold": (
                settings.intelligence_duplicate_confidence_threshold
            ),
            "related_confidence_threshold": (
                settings.intelligence_related_confidence_threshold
            ),
        },
        limitations=limitations,
    )


def list_infrastructure_assets(
    session: Session,
    *,
    asset_type: str | None = None,
    limit: int = 100,
) -> list[InfrastructureAsset]:
    statement = select(InfrastructureAsset).where(
        InfrastructureAsset.is_active.is_(True)
    )
    if asset_type:
        statement = statement.where(
            InfrastructureAsset.asset_type == asset_type
        )
    return list(
        session.scalars(
            statement.order_by(InfrastructureAsset.name).limit(limit)
        ).all()
    )
