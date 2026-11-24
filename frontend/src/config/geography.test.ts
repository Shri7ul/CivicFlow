import { describe, expect, it } from "vitest";

import {
  DEFAULT_GEOGRAPHIC_CONTEXT,
  GEOGRAPHIC_CONTEXTS,
  geographicContextConfig,
  isRegisteredGeographicContext,
  mapViewForContext,
} from "./geography";
import { DEFAULT_MAP_VIEW } from "@/lib/map";

describe("geographic configuration", () => {
  it("registers exactly the two known research contexts", () => {
    expect(GEOGRAPHIC_CONTEXTS.map((item) => item.key)).toEqual([
      "BD-DHAKA",
      "US-NYC",
    ]);
    expect(isRegisteredGeographicContext("BD-DHAKA")).toBe(true);
    expect(isRegisteredGeographicContext("NYC-DHAKA")).toBe(false);
  });

  it("never marks a research context as pilot eligible", () => {
    for (const context of GEOGRAPHIC_CONTEXTS) {
      expect(context.isPilotEligible).toBe(false);
      expect(context.researchOnly).toBe(true);
    }
  });

  it("derives the map viewport from the registered context", () => {
    expect(DEFAULT_GEOGRAPHIC_CONTEXT).toBe("BD-DHAKA");
    expect(DEFAULT_MAP_VIEW).toEqual({
      longitude: 90.4125,
      latitude: 23.8103,
      zoom: 11.5,
    });
    expect(mapViewForContext("US-NYC")).toEqual({
      longitude: -73.98,
      latitude: 40.72,
      zoom: 10.5,
    });
    expect(mapViewForContext("UNREGISTERED").longitude).toBe(90.4125);
  });

  it("keeps Dhaka and NYC envelopes separate", () => {
    const dhaka = geographicContextConfig("BD-DHAKA");
    const nyc = geographicContextConfig("US-NYC");
    expect(dhaka?.bboxGeoJson).toEqual([90.3, 23.68, 90.5, 23.9]);
    expect(nyc?.bboxGeoJson).toEqual([-74.3, 40.4, -73.6, 41.0]);
  });
});
