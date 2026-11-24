"""Registered geographic contexts, boundaries and pilot-area candidates.

Design rules (Phase 12):

* ``US-NYC`` and ``BD-DHAKA`` are *research/context identities*, never proof
  that a dataset is operational or human-verified for that geography.
* A context's bbox is a **screening envelope**, not an authoritative legal or
  administrative boundary. The boundary status is recorded explicitly.
* Resolution from coordinates is conservative: ambiguous or out-of-range
  coordinates return ``UNKNOWN``. Nothing is silently relabelled.
* Historical NYC datasets keep their original keys, hashes, provenance and
  snapshot files. This registry only adds an explicit context label.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

UNKNOWN_CONTEXT_KEY = "UNKNOWN"


class GeographicContextKind(str, Enum):
    RESEARCH = "RESEARCH"
    PILOT_CANDIDATE = "PILOT_CANDIDATE"
    OPERATIONAL = "OPERATIONAL"


class BoundaryStatus(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    PROVISIONAL = "PROVISIONAL"
    NOT_ASSESSED = "NOT_ASSESSED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class BoundingBox:
    """WGS84 bounding box in GeoJSON order: (west, south, east, north)."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        values = (self.west, self.south, self.east, self.north)
        if not all(isinstance(value, (int, float)) for value in values):
            raise ValueError("bbox components must be numeric")
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("bbox longitude range is invalid")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("bbox latitude range is invalid")

    @classmethod
    def from_geojson(cls, values: Iterable[float]) -> "BoundingBox":
        west, south, east, north = (float(value) for value in tuple(values))
        return cls(west, south, east, north)

    @classmethod
    def from_latlon(
        cls, lat_min: float, lon_min: float, lat_max: float, lon_max: float
    ) -> "BoundingBox":
        """Build from the (lat_min, lon_min, lat_max, lon_max) convention.

        This is the convention used by the Phase 8/9/11 dataset specs. Keeping
        the conversion here prevents the three historical bbox orderings from
        being mixed by hand in new code.
        """
        return cls(float(lon_min), float(lat_min), float(lon_max), float(lat_max))

    def as_geojson(self) -> list[float]:
        return [self.west, self.south, self.east, self.north]

    def as_latlon(self) -> tuple[float, float, float, float]:
        return (self.south, self.west, self.north, self.east)

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.south <= latitude <= self.north
            and self.west <= longitude <= self.east
        )

    def contains_bbox(self, other: "BoundingBox") -> bool:
        return (
            self.west <= other.west
            and self.south <= other.south
            and self.east >= other.east
            and self.north >= other.north
        )


@dataclass(frozen=True)
class GeographicContext:
    key: str
    display_name: str
    country_code: str
    country_name: str
    kind: GeographicContextKind
    bbox: BoundingBox
    center_latitude: float
    center_longitude: float
    crs: str
    provenance_basis: str
    boundary_basis: str
    boundary_status: BoundaryStatus
    operational_authority: str | None
    is_pilot_eligible: bool
    source_urls: tuple[str, ...]
    notes: str

    def serialize(self) -> dict:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "kind": self.kind.value,
            "bbox_geojson": self.bbox.as_geojson(),
            "bbox_latlon": list(self.bbox.as_latlon()),
            "center": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "crs": self.crs,
            "provenance_basis": self.provenance_basis,
            "boundary_basis": self.boundary_basis,
            "boundary_status": self.boundary_status.value,
            "operational_authority": self.operational_authority,
            "is_pilot_eligible": self.is_pilot_eligible,
            "source_urls": list(self.source_urls),
            "notes": self.notes,
        }


US_NYC = GeographicContext(
    key="US-NYC",
    display_name="New York City (research and historical validation)",
    country_code="US",
    country_name="United States",
    kind=GeographicContextKind.RESEARCH,
    bbox=BoundingBox(-74.3, 40.4, -73.6, 41.0),
    center_latitude=40.72,
    center_longitude=-73.98,
    crs="EPSG:4326",
    provenance_basis=(
        "Public municipal research datasets acquired in Phases 8-11. Retained "
        "for reproducibility, pipeline testing and comparative experiments."
    ),
    boundary_basis=(
        "Screening envelope used by the NYC bridge acquisition control "
        "(lat 40.4-41.0, lon -74.3--73.6). It is not a legal city boundary."
    ),
    boundary_status=BoundaryStatus.NOT_ASSESSED,
    operational_authority=None,
    is_pilot_eligible=False,
    source_urls=(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
        "https://data.cityofnewyork.us/resource/4yue-vjfc.json",
    ),
    notes=(
        "Historical research geography only. NYC results must never be "
        "reported as Dhaka or Bangladesh model performance, and NYC assets "
        "must never render as Dhaka pilot infrastructure."
    ),
)

BD_DHAKA = GeographicContext(
    key="BD-DHAKA",
    display_name="Dhaka, Bangladesh (research / pilot candidate)",
    country_code="BD",
    country_name="Bangladesh",
    kind=GeographicContextKind.PILOT_CANDIDATE,
    bbox=BoundingBox(90.30, 23.68, 90.50, 23.90),
    center_latitude=23.8103,
    center_longitude=90.4125,
    crs="EPSG:4326",
    provenance_basis=(
        "Central Dhaka screening envelope and OSM-derived infrastructure "
        "context. No authoritative DNCC/DSCC/RAJUK boundary has been acquired, "
        "so this context is not an administrative geography."
    ),
    boundary_basis=(
        "Rectangular screening envelope around central Dhaka. Individual "
        "pillars (DNCC, DSCC, ward, drainage, flood) are NOT_ASSSESSED until "
        "authoritative layers are acquired and provenance-checked."
    ),
    boundary_status=BoundaryStatus.BLOCKED,
    operational_authority=None,
    is_pilot_eligible=False,
    source_urls=(
        "https://www.openstreetmap.org/copyright",
        "https://overpass-api.de/api/interpreter",
    ),
    notes=(
        "Pilot candidate only. No approved pilot area, no stakeholder "
        "agreement, no operational ground truth and no model activation."
    ),
)

CONTEXTS: dict[str, GeographicContext] = {
    US_NYC.key: US_NYC,
    BD_DHAKA.key: BD_DHAKA,
}


@dataclass(frozen=True)
class PilotAreaCandidate:
    name: str
    context_key: str
    bbox: BoundingBox
    basis: str
    status: str
    rationale: str
    blockers: tuple[str, ...]

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "context_key": self.context_key,
            "bbox_geojson": self.bbox.as_geojson(),
            "basis": self.basis,
            "status": self.status,
            "rationale": self.rationale,
            "blockers": list(self.blockers),
        }


# Central Dhaka research cell used for the bounded real OSM acquisition.
# This is an observation cell, not a ward or an approved pilot boundary.
DHAKA_OSM_RESEARCH_CELL = BoundingBox(90.390, 23.780, 90.410, 23.800)

PILOT_AREA_CANDIDATES: tuple[PilotAreaCandidate, ...] = (
    PilotAreaCandidate(
        name="Central Dhaka OSM research cell",
        context_key=BD_DHAKA.key,
        bbox=DHAKA_OSM_RESEARCH_CELL,
        basis="OSM-derived research cell with a real bounded Overpass count verified 2026-11-25",
        status="NOT_ASSESSED",
        rationale=(
            "Small, bounded, geospatially consistent area with verifiable "
            "public infrastructure context; suitable for pipeline rehearsal only."
        ),
        blockers=(
            "No authoritative DNCC/DSCC/ward boundary acquired",
            "No civic complaint dataset for this geography",
            "No field observers or reviewers assigned",
            "No stakeholder agreement or approval",
        ),
    ),
    PilotAreaCandidate(
        name="Ward 14, DNCC (publicly reported works area)",
        context_key=BD_DHAKA.key,
        bbox=BoundingBox(90.370, 23.705, 90.395, 23.730),
        basis=(
            "Public reporting describes DNCC road/drain/footpath works in "
            "West Shewrapara, West Kazipara and Senpara Parbata, Ward 14"
        ),
        status="NOT_ASSESSED",
        rationale="Named ward with documented civic works; useful operational context if boundaries are acquired.",
        blockers=(
            "Ward polygon not acquired from an authoritative source",
            "Reported works are not an incident or complaint dataset",
            "No stakeholder agreement or approval",
        ),
    ),
    PilotAreaCandidate(
        name="Central DSCC wards",
        context_key=BD_DHAKA.key,
        bbox=BoundingBox(90.390, 23.710, 90.430, 23.760),
        basis="Dhaka South City Corporation candidate area; no boundary acquired",
        status="NOT_ASSESSED",
        rationale="Included to avoid excluding the southern city corporation without evidence.",
        blockers=(
            "No DSCC boundary or ward dataset acquired",
            "No source availability assessment completed",
            "No stakeholder agreement or approval",
        ),
    ),
)


def all_contexts() -> tuple[GeographicContext, ...]:
    return tuple(CONTEXTS.values())


def get_context(key: str | None) -> GeographicContext | None:
    return CONTEXTS.get(key or "")


def require_context(key: str | None) -> GeographicContext:
    context = get_context(key)
    if context is None:
        raise ValueError(
            f"Unknown geographic context {key!r}; registered contexts: "
            + ", ".join(sorted(CONTEXTS))
        )
    return context


def assert_context_known(key: str | None) -> str:
    return require_context(key).key


def resolve_context_from_point(latitude: float, longitude: float) -> str:
    for context in CONTEXTS.values():
        if context.bbox.contains(latitude, longitude):
            return context.key
    return UNKNOWN_CONTEXT_KEY


def resolve_context_from_bbox(
    bbox: BoundingBox, *, strict: bool = True
) -> str:
    """Resolve a bbox whose full extent lies inside a registered context.

    With ``strict=False`` a centroid/coverage overlap may resolve, but the
    default rejects partially overlapping or ambiguous extents.
    """
    matches = [
        context for context in CONTEXTS.values() if context.bbox.contains_bbox(bbox)
    ]
    if len(matches) == 1:
        return matches[0].key
    if not strict and matches:
        return matches[0].key
    return UNKNOWN_CONTEXT_KEY


def pilot_area_selection_status() -> dict:
    """Final pilot selection is blocked unless a stakeholder-approved area exists."""
    return {
        "status": "BLOCKED",
        "selected_area": None,
        "reason": (
            "No authoritative boundary, approved stakeholder agreement or "
            "operational ground-truth capability exists. Candidates are a "
            "transparent shortlist only."
        ),
        "candidates": [item.serialize() for item in PILOT_AREA_CANDIDATES],
    }
