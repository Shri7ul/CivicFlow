"""Phase 11 fresh external-validation slices.

These are intentionally separate from NYC311_DATASETS so the historical Phase
8/9 registry and its reported results remain reproducible. Q3 2026 is a
post-Phase-9 temporal holdout relative to the 2025 development slices.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.validation.dataset import NYC311DatasetSpec

PHASE11_BROOKLYN_Q3 = NYC311DatasetSpec(
    dataset_key="nyc311-brooklyn-2026q3",
    name="NYC 311 Brooklyn Q3 2026 fresh external slice",
    description=(
        "Fresh post-development temporal holdout using the same Brooklyn bbox and "
        "complaint-type selection as the 2025 slices. Public service-request "
        "activity, not verified hazard impact or ground truth."
    ),
    region="Brooklyn, New York City (bbox 40.680,-73.990 to 40.710,-73.950)",
    bbox=(40.680, -73.990, 40.710, -73.950),
    period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
    period_end=datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_brooklyn_2026q3.json.gz",
)
PHASE11_MANHATTAN_Q3 = NYC311DatasetSpec(
    dataset_key="nyc311-manhattan-2026q3",
    name="NYC 311 Manhattan Q3 2026 fresh external slice",
    description=(
        "Fresh post-development temporal and cross-region holdout using the same "
        "Manhattan bbox and complaint-type selection as the 2025 slice. Public "
        "service-request activity, not verified hazard impact."
    ),
    region="Manhattan, New York City (bbox 40.705,-73.995 to 40.745,-73.955)",
    bbox=(40.705, -73.995, 40.745, -73.955),
    period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
    period_end=datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_manhattan_2026q3.json.gz",
)

PHASE11_DATASETS: dict[str, NYC311DatasetSpec] = {
    spec.dataset_key: spec
    for spec in (PHASE11_BROOKLYN_Q3, PHASE11_MANHATTAN_Q3)
}
