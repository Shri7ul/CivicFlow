import { describe, expect, it } from "vitest";

import {
  BASEMAP_TILES,
  FALLBACK_TILES,
  incidentToFeature,
  incidentsToGeoJSON,
  OSM_STYLE,
  selectedIncidentGeoJSON,
} from "@/lib/map";
import type { Incident } from "@/types/incidents";

const incident: Incident = {
  id: "incident-1",
  title: "Blocked drain",
  description: "Water is pooling.",
  category: "DRAINAGE",
  severity: "HIGH",
  status: "OPEN",
  latitude: 23.8103,
  longitude: 90.4125,
  address: null,
  reporter: { id: "profile-1", full_name: "Citizen" },
  assigned_department: null,
  resolved_at: null,
  created_at: "2026-11-24T00:00:00Z",
  updated_at: "2026-11-24T00:00:00Z",
  history: [],
  evidence: [],
};

describe("basemap configuration", () => {
  it("uses key-free Esri World Dark Gray as the primary basemap", () => {
    const tiles = OSM_STYLE.sources.osm.tiles;
    expect(tiles).toEqual(BASEMAP_TILES);
    expect(tiles.join(" ")).toContain(
      "server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base",
    );
    expect(tiles.join(" ")).toContain("{z}/{y}/{x}");
    expect(tiles.join(" ")).not.toContain("tile.openstreetmap.org");
    expect(tiles.join(" ")).not.toContain("@2x");
  });

  it("falls back to a second clean Esri host and credits providers", () => {
    const fallback = FALLBACK_TILES.join(" ");
    expect(fallback).toContain(
      "services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base",
    );
    expect(fallback).toContain("{z}/{y}/{x}");
    expect(fallback).not.toContain("basemaps.cartocdn.com");
    const attribution = OSM_STYLE.sources.osm.attribution;
    expect(attribution).toContain("OpenStreetMap");
    expect(attribution).toContain("Esri");
  });
});

describe("incident map helpers", () => {
  it("creates a GeoJSON point with encoded properties", () => {
    const feature = incidentToFeature(incident);
    expect(feature.geometry.coordinates).toEqual([90.4125, 23.8103]);
    expect(feature.properties).toMatchObject({
      id: "incident-1",
      category: "DRAINAGE",
      categoryLabel: "Drainage",
      categoryShort: "DR",
      severity: "HIGH",
      status: "OPEN",
    });
  });

  it("builds feature collections and selected features", () => {
    const collection = incidentsToGeoJSON([incident]);
    expect(collection.features).toHaveLength(1);
    expect(collection.features[0]?.geometry.type).toBe("Point");

    expect(selectedIncidentGeoJSON(null).features).toHaveLength(0);
    expect(selectedIncidentGeoJSON(incident).features).toHaveLength(1);
  });
});
