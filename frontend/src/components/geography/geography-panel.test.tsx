import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GeographyPanelView } from "./geography-panel";
import type {
  DhakaReadinessReport,
  GeographicContext,
  PilotAreaSelection,
} from "@/types/geography";

const contexts: GeographicContext[] = [
  {
    key: "BD-DHAKA",
    display_name: "Dhaka, Bangladesh (research / pilot candidate)",
    country_code: "BD",
    country_name: "Bangladesh",
    kind: "PILOT_CANDIDATE",
    bbox_geojson: [90.3, 23.68, 90.5, 23.9],
    center_geojson: { latitude: 23.8103, longitude: 90.4125 },
    crs: "EPSG:4326",
    provenance_basis: "OSM-derived research context",
    boundary_basis: "Research screening envelope",
    boundary_status: "BLOCKED",
    operational_authority: null,
    is_pilot_eligible: false,
    source_urls: [],
    notes: "No approved pilot.",
  },
  {
    key: "US-NYC",
    display_name: "New York City (historical research)",
    country_code: "US",
    country_name: "United States",
    kind: "RESEARCH",
    bbox_geojson: [-74.3, 40.4, -73.6, 41.0],
    center_geojson: { latitude: 40.72, longitude: -73.98 },
    crs: "EPSG:4326",
    provenance_basis: "Historical research",
    boundary_basis: "Screening envelope",
    boundary_status: "NOT_ASSESSED",
    operational_authority: null,
    is_pilot_eligible: false,
    source_urls: [],
    notes: "Never Dhaka evidence.",
  },
];

const readiness: DhakaReadinessReport = {
  protocol: "phase12-dhaka-readiness-v1",
  generated_at: "2026-11-25T00:00:00+00:00",
  geographic_context_key: "BD-DHAKA",
  overall: "NOT_READY",
  pilot_activation_authorized: false,
  ready_for_activation: false,
  categories: [
    {
      key: "dhaka_pilot_area_selection",
      label: "Dhaka pilot area selection",
      status: "BLOCKED",
      mandatory: true,
      owner: "Pilot administrator",
      summary: "No approved area",
      criteria: [],
      blocking_issues: ["No approved area"],
    },
  ],
  mandatory_unmet: ["dhaka_pilot_area_selection"],
  advisory_unmet: [],
  blockers: ["Dhaka pilot area selection (BLOCKED): No approved area"],
  disclaimer: "Missing evidence is never PASS.",
  pilot_area_selection: {
    status: "BLOCKED",
    selected_area: null,
    reason: "No stakeholder approval",
    candidates: [],
  },
};

const pilotAreas: PilotAreaSelection = {
  status: "BLOCKED",
  selected_area: null,
  reason: "No stakeholder approval",
  candidates: [
    {
      name: "Central Dhaka OSM research cell",
      context_key: "BD-DHAKA",
      bbox_geojson: [90.39, 23.78, 90.41, 23.8],
      basis: "OSM research cell",
      status: "NOT_ASSESSED",
      rationale: "Small bounded area",
      blockers: ["No boundary"],
    },
  ],
};

describe("GeographyPanelView", () => {
  it("renders only server-provided context and readiness values", () => {
    const html = renderToStaticMarkup(
      <GeographyPanelView
        contexts={contexts}
        selectedContext="BD-DHAKA"
        readiness={readiness}
        pilotAreas={pilotAreas}
        workspace={{ snapshots: [{ snapshot_key: "dhaka-only" }] }}
        error={null}
      />,
    );
    expect(html).toContain("Dhaka, Bangladesh (research / pilot candidate)");
    expect(html).toContain("BLOCKED");
    expect(html).toContain("NOT_READY");
    expect(html).toContain("Activation authorized:");
    expect(html).toContain("NO");
    expect(html).toContain("Central Dhaka OSM research cell");
    expect(html).toContain("Phase 12 preparations only");
  });

  it("does not render NYC assets in a Dhaka-scoped view", () => {
    const html = renderToStaticMarkup(
      <GeographyPanelView
        contexts={contexts}
        selectedContext="BD-DHAKA"
        readiness={readiness}
        pilotAreas={null}
        workspace={{ snapshots: [] }}
        error={null}
      />,
    );
    expect(html).not.toContain("nyc-dot-bridge");
    expect(html).not.toContain("Brooklyn");
    expect(html).toContain("Server-scoped evidence rows for BD-DHAKA: 0");
  });
});
