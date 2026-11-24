"""Geographic context primitives for CivicFlow Phase 12.

This package is the single source of truth for geographic identity. It exists
so that ``BD-DHAKA`` is a registered context rather than an arbitrary string
scattered through the application, and so that historical New York research
data can never be silently reinterpreted as Dhaka operational evidence.
"""

from app.geo.contexts import (
    BD_DHAKA,
    US_NYC,
    UNKNOWN_CONTEXT_KEY,
    BoundingBox,
    GeographicContext,
    GeographicContextKind,
    BoundaryStatus,
    PilotAreaCandidate,
    all_contexts,
    assert_context_known,
    get_context,
    pilot_area_selection_status,
    require_context,
    resolve_context_from_bbox,
    resolve_context_from_point,
)

__all__ = [
    "BD_DHAKA",
    "US_NYC",
    "UNKNOWN_CONTEXT_KEY",
    "BoundingBox",
    "GeographicContext",
    "GeographicContextKind",
    "BoundaryStatus",
    "PilotAreaCandidate",
    "all_contexts",
    "assert_context_known",
    "get_context",
    "pilot_area_selection_status",
    "require_context",
    "resolve_context_from_bbox",
    "resolve_context_from_point",
]
