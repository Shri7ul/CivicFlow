import { describe, expect, it } from "vitest";

import {
  incidentToFeature,
  incidentsToGeoJSON,
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
