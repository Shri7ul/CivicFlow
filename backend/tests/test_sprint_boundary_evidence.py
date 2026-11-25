"""Integrity and safety tests for the 12-hour Dhaka evidence sprint artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "sprint_boundaries"
MANIFEST = DATA / "SPRINT_MANIFEST.json"

PINNED_HASHES = {
    "hdx_cod_ab_bgd_admin_boundaries_geojson.zip": "ec54c97c2004bbee084afa3f662abb202d8ec038dbfd398af2ebb9b1bf3ec9e5",
    "geoboundaries_BGD_ADM4_simplified.geojson": "ce2b675b26abbf347c735f2a834093f736c8238bcc82acad9eeb5e105684124b",
    "civicflow_dhaka_cod_ab_v03_dncc_dscc_candidate.geojson": "34ce0395f0c6b09a20320d3c66d3b3c12a167522a2660671aec544b8f43bee10",
    "civicflow_dhaka_bgisp_official_city_corporations.geojson": "33b586e0f170157bc363ed4d0f306e9bfdf60526200854e16808b1091775701a",
    "civicflow_dhaka_bgisp_official_dncc_dscc_wards.geojson": "15a65b23cc69d6e1ccf6dae2f9c62c4543d7972024c8cab1816ef8bd4632c9be",
    "civicflow_dhaka_adm4_ward_candidates_within_cod_ab.geojson": "b06c1f7648b209afda4835013254f41a11b9efb21e767528c8f87f0c1b50af61",
    "worldbank_BD_SP_URB_TOTL_2015_2025.json": "57e878e61ca05d4b6ce7530c8a36b0f1c78cbc191800fee899bcb67c5b46511d",
}


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _sha256(name: str) -> str:
    return hashlib.sha256((DATA / name).read_bytes()).hexdigest()


def test_manifest_records_versioned_artifacts_with_matching_hashes() -> None:
    manifest = _load("SPRINT_MANIFEST.json")
    versioned = [entry for entry in manifest["artifacts"] if entry["versioned"]]

    assert len(versioned) >= 20
    for entry in versioned:
        assert _sha256(entry["file"]) == entry["sha256"], entry["file"]
        assert (DATA / entry["file"]).stat().st_size == entry["bytes"]


def test_critical_artifacts_have_pinned_hashes() -> None:
    for name, expected in PINNED_HASHES.items():
        assert _sha256(name) == expected, name


def test_sprint_artifacts_are_not_marked_operational() -> None:
    manifest = _load("SPRINT_MANIFEST.json")

    assert "no boundary approved" in manifest["scope"].lower()
    for entry in manifest["artifacts"]:
        assert entry["operational_status"] == "UNVERIFIED_RESEARCH_EVIDENCE"


def test_official_city_boundaries_are_exactly_dncc_and_dscc() -> None:
    payload = _load("civicflow_dhaka_bgisp_official_city_corporations.geojson")

    assert payload["crs"]["properties"]["name"] == "urn:ogc:def:crs:OGC:1.3:CRS84"
    assert len(payload["features"]) == 2
    features = {f["properties"]["city_name"]: f for f in payload["features"]}
    assert set(features) == {
        "Dhaka North City Corporation",
        "Dhaka South City Corporation",
    }
    assert features["Dhaka North City Corporation"]["properties"]["city_geo_code"] == "302625"
    assert features["Dhaka South City Corporation"]["properties"]["city_geo_code"] == "302620"
    assert all(f["geometry"]["type"] in {"Polygon", "MultiPolygon"} for f in payload["features"])


def test_official_ward_candidates_have_expected_counts() -> None:
    payload = _load("civicflow_dhaka_bgisp_official_dncc_dscc_wards.geojson")
    features = payload["features"]

    assert payload["crs"]["properties"]["name"] == "urn:ogc:def:crs:OGC:1.3:CRS84"
    assert len(features) == 164
    counts: dict[str, int] = {}
    for feature in features:
        props = feature["properties"]
        counts[props["city_name"]] = counts.get(props["city_name"], 0) + 1
        assert props["district_geo_code"] == "3026"
        assert props["union_ward_geo_code"]
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert counts == {
        "Dhaka North City Corporation": 76,
        "Dhaka South City Corporation": 88,
    }


def test_cross_source_city_boundaries_agree_within_tolerance() -> None:
    verification = _load("SPRINT_VERIFICATION.json")

    assert len(verification["boundary_comparison"]) == 2
    for comparison in verification["boundary_comparison"]:
        assert comparison["max_bbox_delta_deg"] < 1e-5
    assert verification["bgisp_ward_centroids_inside_parent_city"] == 164
    assert "no boundary approved" in verification["note"].lower()


def test_geoboundaries_candidates_are_bounded_and_not_official() -> None:
    payload = _load("civicflow_dhaka_adm4_ward_candidates_within_cod_ab.geojson")
    features = payload["features"]

    assert len(features) == 138
    assert all(
        feature["properties"]["civicflow_source"].startswith("geoBoundaries")
        for feature in features
    )
    assert all(
        feature["properties"]["civicflow_candidate_parent"]
        in {"Dhaka North City Corporation", "Dhaka South City Corporation"}
        for feature in features
    )
    assert all(90.0 <= feature["properties"]["civicflow_centroid_lon"] <= 91.0 for feature in features)
    assert all(23.0 <= feature["properties"]["civicflow_centroid_lat"] <= 25.0 for feature in features)


def test_worldbank_data_is_national_context_only() -> None:
    metadata, rows = _load("worldbank_BD_SP_URB_TOTL_2015_2025.json")

    assert metadata["sourceid"] == "2"
    assert metadata["total"] == 11
    assert metadata["lastupdated"] == "2026-11-11"
    assert rows[0]["countryiso3code"] == "BGD"
    assert all(row["indicator"]["id"] == "SP.URB.TOTL" for row in rows)
