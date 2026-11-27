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
  it("uses a policy-compliant CARTO basemap instead of the blocked OSM tile host", () => {
    const tiles = OSM_STYLE.sources.osm.tiles;
    expect(tiles).toEqual(BASEMAP_TILES);
    expect(tiles.join(" ")).not.toContain("tile.openstreetmap.org");
    expect(tiles.join(" ")).toContain("basemaps.cartocdn.com/dark_all");
  });

  it("falls back to Esri dark tiles and credits every provider", () => {
    expect(FALLBACK_TILES.join(" ")).toContain(
      "server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base",
    );
    expect(FALLBACK_TILES.join(" ")).toContain("{z}/{y}/{x}");
    const attribution = OSM_STYLE.sources.osm.attribution;
    expect(attribution).toContain("CARTO");
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
