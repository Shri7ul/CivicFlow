"""Small WGS84 geometry helpers shared by the risk engine.

PostGIS remains authoritative for database filtering and distance where
available. These helpers support H3 cell/asset association and portable tests.
"""

from __future__ import annotations

import math
import re

_WKT_RE = re.compile(r"^\s*(POINT|LINESTRING|POLYGON)\s*\((.*)\)\s*$", re.I)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def _vertices(value: str) -> tuple[str, list[tuple[float, float]]]:
    match = _WKT_RE.match(value or "")
    if not match:
        raise ValueError("Unsupported WKT geometry")
    geometry_type = match.group(1).upper()
    body = match.group(2).strip()
    if geometry_type == "POLYGON":
        body = body.strip("()").split("),", 1)[0].strip("()")
    points: list[tuple[float, float]] = []
    for pair in body.split(","):
        parts = pair.strip().strip("()").split()
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))
    if not points:
        raise ValueError("WKT geometry has no coordinates")
    return geometry_type, points


def _point_in_polygon(
    latitude: float,
    longitude: float,
    points: list[tuple[float, float]],
) -> bool:
    """Ray casting for a WKT outer ring in lon/lat order.

    The polygon boundary remains authoritative for edge distance. This test
    prevents a facility polygon that contains the cell centre from being
    reported as several hundred metres away merely because its boundary is far
    from the centre.
    """
    if len(points) < 3:
        return False
    x = longitude
    y = latitude
    inside = False
    previous_x, previous_y = points[-1]
    for current_x, current_y in points:
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            denominator = previous_y - current_y
            if denominator != 0:
                intersection_x = (
                    (previous_x - current_x)
                    * (y - current_y)
                    / denominator
                    + current_x
                )
                if x < intersection_x:
                    inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _segment_distance(
    first: tuple[float, float],
    second: tuple[float, float],
    origin_latitude: float,
    origin_longitude: float,
) -> float:
    cos_lat = math.cos(math.radians(origin_latitude))
    ax = (first[0] - origin_longitude) * 111_320 * cos_lat
    ay = (first[1] - origin_latitude) * 110_540
    bx = (second[0] - origin_longitude) * 111_320 * cos_lat
    by = (second[1] - origin_latitude) * 110_540
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, (-ax * dx - ay * dy) / length_squared))
    return math.hypot(ax + t * dx, ay + t * dy)


def geometry_distance_m(
    latitude: float,
    longitude: float,
    geometry_wkt: str,
) -> float:
    geometry_type, points = _vertices(geometry_wkt)
    if geometry_type == "POINT" or len(points) == 1:
        return haversine_m(latitude, longitude, points[0][1], points[0][0])
    if geometry_type == "POLYGON" and _point_in_polygon(
        latitude, longitude, points
    ):
        return 0.0
    distances = [
        _segment_distance(points[index], points[index + 1], latitude, longitude)
        for index in range(len(points) - 1)
    ]
    if geometry_type == "POLYGON" and len(points) > 1:
        distances.append(
            _segment_distance(points[-1], points[0], latitude, longitude)
        )
    return min(distances) if distances else math.inf


def bbox_contains(
    latitude: float,
    longitude: float,
    bbox: tuple[float, float, float, float] | None,
) -> bool:
    if bbox is None:
        return True
    min_lat, min_lon, max_lat, max_lon = bbox
    return min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon
