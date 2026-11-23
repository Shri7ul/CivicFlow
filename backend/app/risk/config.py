"""Validated, versioned configuration for the urban risk model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from app.core.config import Settings
from app.models import IncidentCategory, IncidentSeverity, RiskCategory

FACTOR_KEYS = (
    "severity",
    "density",
    "spatial",
    "recency",
    "active",
    "category",
    "trend",
    "infrastructure",
    "dependency",
)

FACTOR_LABELS = {
    "severity": "Incident severity",
    "density": "Adjusted incident density",
    "spatial": "Spatial concentration",
    "recency": "Recency",
    "active": "Active incident share",
    "category": "Category consequence",
    "trend": "Temporal trend",
    "infrastructure": "Infrastructure exposure",
    "dependency": "Dependency context",
}

DEFAULT_SEVERITY_WEIGHTS: Mapping[IncidentSeverity, float] = {
    IncidentSeverity.LOW: 0.10,
    IncidentSeverity.MEDIUM: 0.35,
    IncidentSeverity.HIGH: 0.70,
    IncidentSeverity.CRITICAL: 1.00,
}

DEFAULT_CATEGORY_WEIGHTS: Mapping[IncidentCategory, float] = {
    IncidentCategory.DRAINAGE: 0.85,
    IncidentCategory.ROADS: 0.70,
    IncidentCategory.PUBLIC_SAFETY: 0.90,
    IncidentCategory.HEALTH: 0.80,
    IncidentCategory.UTILITIES: 0.65,
    IncidentCategory.SANITATION: 0.55,
    IncidentCategory.ENVIRONMENT: 0.55,
    IncidentCategory.OTHER: 0.30,
}

CATEGORY_ORDER = (
    RiskCategory.MINIMAL,
    RiskCategory.LOW,
    RiskCategory.MODERATE,
    RiskCategory.HIGH,
    RiskCategory.CRITICAL,
)

CATEGORY_LABELS = {
    RiskCategory.MINIMAL: "Minimal",
    RiskCategory.LOW: "Low",
    RiskCategory.MODERATE: "Moderate",
    RiskCategory.HIGH: "High",
    RiskCategory.CRITICAL: "Critical",
}

CATEGORY_COLORS = {
    RiskCategory.MINIMAL: "#64748b",
    RiskCategory.LOW: "#38bdf8",
    RiskCategory.MODERATE: "#fbbf24",
    RiskCategory.HIGH: "#fb923c",
    RiskCategory.CRITICAL: "#fb7185",
}


class RiskConfigError(ValueError):
    """Raised when risk configuration is internally inconsistent."""


@dataclass(frozen=True)
class RiskBand:
    category: RiskCategory
    min_score: float
    max_score: float
    label: str
    color: str


@dataclass(frozen=True)
class RiskConfig:
    model_version: str
    default_resolution: int
    min_resolution: int
    max_resolution: int
    default_window_hours: int
    max_window_hours: int
    recency_half_life_hours: float
    density_saturation: int
    infrastructure_radius_m: int
    max_incidents: int
    max_cells: int
    privacy_min_incidents: int
    trend_min_incidents: int
    weights: Mapping[str, float]
    threshold_low: float
    threshold_moderate: float
    threshold_high: float
    threshold_critical: float
    severity_weights: Mapping[IncidentSeverity, float] = field(
        default_factory=lambda: dict(DEFAULT_SEVERITY_WEIGHTS)
    )
    category_weights: Mapping[IncidentCategory, float] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_WEIGHTS)
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))
        object.__setattr__(
            self,
            "severity_weights",
            MappingProxyType(dict(self.severity_weights)),
        )
        object.__setattr__(
            self,
            "category_weights",
            MappingProxyType(dict(self.category_weights)),
        )
        if not self.model_version.strip():
            raise RiskConfigError("risk model version must not be empty")
        if not 5 <= self.min_resolution <= self.default_resolution <= self.max_resolution <= 12:
            raise RiskConfigError(
                "H3 resolutions must satisfy min <= default <= max within 5..12"
            )
        if not 1 <= self.default_window_hours <= self.max_window_hours:
            raise RiskConfigError(
                "default window must be positive and <= max window"
            )
        if self.recency_half_life_hours <= 0:
            raise RiskConfigError("recency half-life must be positive")
        if self.density_saturation < 1:
            raise RiskConfigError("density saturation must be positive")
        if self.infrastructure_radius_m <= 0:
            raise RiskConfigError("infrastructure radius must be positive")
        if self.max_incidents < 1 or self.max_cells < 1:
            raise RiskConfigError("max incident/cell bounds must be positive")
        if not 1 <= self.privacy_min_incidents <= 20:
            raise RiskConfigError("privacy minimum must be within 1..20")
        if not 2 <= self.trend_min_incidents <= 20:
            raise RiskConfigError("trend minimum must be within 2..20")
        if set(self.weights) != set(FACTOR_KEYS):
            missing = sorted(set(FACTOR_KEYS) - set(self.weights))
            unexpected = sorted(set(self.weights) - set(FACTOR_KEYS))
            raise RiskConfigError(
                "factor weights must define exactly the configured factors; "
                f"missing={missing}, unexpected={unexpected}"
            )
        if any(weight < 0 for weight in self.weights.values()):
            raise RiskConfigError("factor weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise RiskConfigError("factor weights must sum to 1.0")
        thresholds = self.thresholds
        if not 0 < thresholds[0] < thresholds[1] < thresholds[2] < thresholds[3] < 100:
            raise RiskConfigError(
                "risk thresholds must be strictly ascending within (0, 100)"
            )
        if set(self.severity_weights) != set(IncidentSeverity):
            raise RiskConfigError(
                "severity weights must define every IncidentSeverity"
            )
        if set(self.category_weights) != set(IncidentCategory):
            raise RiskConfigError(
                "category weights must define every IncidentCategory"
            )
        if any(not 0 <= value <= 1 for value in self.severity_weights.values()):
            raise RiskConfigError("severity weights must be within 0..1")
        if any(not 0 <= value <= 1 for value in self.category_weights.values()):
            raise RiskConfigError("category weights must be within 0..1")

    @property
    def thresholds(self) -> tuple[float, float, float, float]:
        return (
            self.threshold_low,
            self.threshold_moderate,
            self.threshold_high,
            self.threshold_critical,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "RiskConfig":
        return cls(
            model_version=settings.risk_model_version,
            default_resolution=settings.risk_default_resolution,
            min_resolution=settings.risk_min_resolution,
            max_resolution=settings.risk_max_resolution,
            default_window_hours=settings.risk_default_window_hours,
            max_window_hours=settings.risk_max_window_hours,
            recency_half_life_hours=float(settings.risk_recency_half_life_hours),
            density_saturation=settings.risk_density_saturation,
            infrastructure_radius_m=settings.risk_infrastructure_radius_m,
            max_incidents=settings.risk_max_incidents,
            max_cells=settings.risk_max_cells,
            privacy_min_incidents=settings.risk_privacy_min_incidents,
            trend_min_incidents=settings.risk_trend_min_incidents,
            weights={
                "severity": settings.risk_weight_severity,
                "density": settings.risk_weight_density,
                "spatial": settings.risk_weight_spatial,
                "recency": settings.risk_weight_recency,
                "active": settings.risk_weight_active,
                "category": settings.risk_weight_category,
                "trend": settings.risk_weight_trend,
                "infrastructure": settings.risk_weight_infrastructure,
                "dependency": settings.risk_weight_dependency,
            },
            threshold_low=settings.risk_threshold_low,
            threshold_moderate=settings.risk_threshold_moderate,
            threshold_high=settings.risk_threshold_high,
            threshold_critical=settings.risk_threshold_critical,
        )

    @property
    def bands(self) -> tuple[RiskBand, ...]:
        boundaries = (0.0, *self.thresholds, 100.0)
        return tuple(
            RiskBand(
                category=category,
                min_score=boundaries[index],
                max_score=boundaries[index + 1],
                label=CATEGORY_LABELS[category],
                color=CATEGORY_COLORS[category],
            )
            for index, category in enumerate(CATEGORY_ORDER)
        )

    def category_for(self, score: float) -> RiskCategory:
        if score >= self.threshold_critical:
            return RiskCategory.CRITICAL
        if score >= self.threshold_high:
            return RiskCategory.HIGH
        if score >= self.threshold_moderate:
            return RiskCategory.MODERATE
        if score >= self.threshold_low:
            return RiskCategory.LOW
        return RiskCategory.MINIMAL

    def as_dict(self) -> dict:
        return {
            "model_version": self.model_version,
            "resolutions": {
                "min": self.min_resolution,
                "default": self.default_resolution,
                "max": self.max_resolution,
            },
            "windows": {
                "default_hours": self.default_window_hours,
                "max_hours": self.max_window_hours,
            },
            "recency_half_life_hours": self.recency_half_life_hours,
            "density_saturation": self.density_saturation,
            "infrastructure_radius_m": self.infrastructure_radius_m,
            "max_incidents": self.max_incidents,
            "max_cells": self.max_cells,
            "privacy_min_incidents": self.privacy_min_incidents,
            "trend_min_incidents": self.trend_min_incidents,
            "weights": dict(self.weights),
            "severity_weights": {
                key.value: value for key, value in self.severity_weights.items()
            },
            "category_weights": {
                key.value: value for key, value in self.category_weights.items()
            },
            "bands": [
                {
                    "category": band.category.value,
                    "label": band.label,
                    "color": band.color,
                    "min_score": band.min_score,
                    "max_score": band.max_score,
                }
                for band in self.bands
            ],
        }

    @property
    def config_hash(self) -> str:
        payload = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
