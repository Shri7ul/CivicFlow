"""Synthetic, explicitly labelled validation of Phase 4 duplicate scoring.

No labelled municipal duplicate ground truth exists in the selected NYC 311
dataset. These hand-constructed cases exercise the actual scoring function and
must never be presented as field precision/recall.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models import (
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)
from app.services.intelligence import _score_candidate, haversine_m

BASE = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def _incident(
    number: int,
    *,
    title: str,
    category: IncidentCategory,
    latitude: float,
    longitude: float,
    minutes: int,
    severity: IncidentSeverity = IncidentSeverity.MEDIUM,
    status: IncidentStatus = IncidentStatus.OPEN,
) -> Incident:
    return Incident(
        id=uuid.UUID(int=number),
        title=title,
        description=title,
        category=category,
        severity=severity,
        status=status,
        location=f"POINT({longitude:.8f} {latitude:.8f})",
        reporter_id=uuid.UUID(int=999999),
        created_at=BASE + timedelta(minutes=minutes),
    )


def _cases() -> list[dict]:
    return [
        {
            "case": "duplicate_road_pothole",
            "origin": _incident(
                1,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6900,
                longitude=-73.9800,
                minutes=0,
            ),
            "candidate": _incident(
                2,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6902,
                longitude=-73.9800,
                minutes=10,
            ),
            "expected_duplicate": True,
        },
        {
            "case": "duplicate_sanitation_missed_collection",
            "origin": _incident(
                3,
                title="Missed garbage collection",
                category=IncidentCategory.SANITATION,
                latitude=40.7000,
                longitude=-73.9600,
                minutes=0,
            ),
            "candidate": _incident(
                4,
                title="Missed garbage collection",
                category=IncidentCategory.SANITATION,
                latitude=40.7005,
                longitude=-73.9601,
                minutes=45,
            ),
            "expected_duplicate": True,
        },
        {
            "case": "duplicate_related_road_drainage",
            "origin": _incident(
                5,
                title="Flooded road blocked by drain",
                category=IncidentCategory.ROADS,
                latitude=40.7050,
                longitude=-73.9700,
                minutes=0,
                severity=IncidentSeverity.HIGH,
            ),
            "candidate": _incident(
                6,
                title="Flooded road blocked by drain",
                category=IncidentCategory.DRAINAGE,
                latitude=40.7056,
                longitude=-73.9702,
                minutes=90,
                severity=IncidentSeverity.HIGH,
            ),
            "expected_duplicate": True,
        },
        {
            "case": "duplicate_utility_heat",
            "origin": _incident(
                7,
                title="No heat in apartment building",
                category=IncidentCategory.UTILITIES,
                latitude=40.6850,
                longitude=-73.9750,
                minutes=0,
                severity=IncidentSeverity.HIGH,
            ),
            "candidate": _incident(
                8,
                title="No heat in apartment building",
                category=IncidentCategory.UTILITIES,
                latitude=40.6854,
                longitude=-73.9752,
                minutes=120,
                severity=IncidentSeverity.HIGH,
            ),
            "expected_duplicate": True,
        },
        {
            "case": "non_duplicate_far_apart",
            "origin": _incident(
                9,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6900,
                longitude=-73.9800,
                minutes=0,
            ),
            "candidate": _incident(
                10,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6940,
                longitude=-73.9800,
                minutes=10,
            ),
            "expected_duplicate": False,
        },
        {
            "case": "non_duplicate_outside_time_window",
            "origin": _incident(
                11,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6900,
                longitude=-73.9800,
                minutes=0,
            ),
            "candidate": _incident(
                12,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6902,
                longitude=-73.9800,
                minutes=60 * 30,
            ),
            "expected_duplicate": False,
        },
        {
            "case": "non_duplicate_different_problem",
            "origin": _incident(
                13,
                title="Pothole on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6900,
                longitude=-73.9800,
                minutes=0,
            ),
            "candidate": _incident(
                14,
                title="Streetlight outage on Atlantic Avenue",
                category=IncidentCategory.ROADS,
                latitude=40.6901,
                longitude=-73.9800,
                minutes=10,
            ),
            "expected_duplicate": False,
        },
        {
            "case": "non_duplicate_unrelated_category",
            "origin": _incident(
                15,
                title="Missed garbage collection",
                category=IncidentCategory.SANITATION,
                latitude=40.7000,
                longitude=-73.9600,
                minutes=0,
            ),
            "candidate": _incident(
                16,
                title="Traffic signal controller failure",
                category=IncidentCategory.ROADS,
                latitude=40.7001,
                longitude=-73.9601,
                minutes=30,
            ),
            "expected_duplicate": False,
        },
    ]


def run_correlation_validation(settings: Settings) -> dict:
    results = []
    tp = fp = tn = fn = 0
    for case in _cases():
        origin = case["origin"]
        candidate = case["candidate"]
        origin_lat, origin_lon = 40.69, -73.98
        # Use the WKT coordinates rather than UI-only helper state.
        from app.services.incidents import parse_point

        origin_lat, origin_lon = parse_point(origin.location)
        candidate_lat, candidate_lon = parse_point(candidate.location)
        distance = haversine_m(
            origin_lat, origin_lon, candidate_lat, candidate_lon
        )
        scored = _score_candidate(
            origin, candidate, distance_m=distance, settings=settings
        )
        predicted = scored.is_duplicate
        expected = case["expected_duplicate"]
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif not predicted and expected:
            fn += 1
        else:
            tn += 1
        results.append(
            {
                "case": case["case"],
                "expected_duplicate": expected,
                "predicted_duplicate": predicted,
                "distance_m": scored.distance_m,
                "time_delta_seconds": scored.time_delta_seconds,
                "text_similarity": scored.text_similarity,
                "confidence": scored.confidence,
            }
        )
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "status": "COMPLETED" if tp + fn else "INSUFFICIENT_DATA",
        "case_count": len(results),
        "positive_count": tp + fn,
        "negative_count": tn + fp,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "f1": round(f1, 6) if f1 is not None else None,
        "cases": results,
        "thresholds": {
            "duplicate_radius_m": settings.intelligence_duplicate_radius_m,
            "duplicate_window_hours": settings.intelligence_duplicate_window_hours,
            "text_threshold": settings.intelligence_duplicate_text_threshold,
            "confidence_threshold": (
                settings.intelligence_duplicate_confidence_threshold
            ),
        },
    }
