import { describe, expect, it, vi } from "vitest";

import {
  buildRiskQuery,
  getRiskCell,
  getRiskCellsGeoJSON,
  getRiskConfig,
  getRiskInfrastructureExposure,
  getRiskSummary,
  getRiskTrends,
  listRiskCells,
} from "@/lib/api/risk";

describe("risk API helpers", () => {
  it("serializes bounded spatial and temporal filters", () => {
    const query = buildRiskQuery({
      resolution: 8,
      window: "7d",
      minLatitude: 23.7,
      minLongitude: 90.3,
      maxLatitude: 23.9,
      maxLongitude: 90.5,
      minScore: 40,
      category: "HIGH",
      limit: 100,
      offset: 20,
    });
    expect(query).toContain("resolution=8");
    expect(query).toContain("window=7d");
    expect(query).toContain("min_latitude=23.7");
    expect(query).toContain("min_score=40");
    expect(query).toContain("category=HIGH");
    expect(query).toContain("limit=100");
    expect(query).toContain("offset=20");
  });

  it("omits invalid partial bboxes", () => {
    expect(buildRiskQuery({ minLatitude: 23.7, maxLatitude: 23.9 })).toBe("");
  });

  it("requests config, cells, GeoJSON, summary, trends, and exposure", async () => {
    const request = vi.fn(async (path: string) => ({ path }));
    await getRiskConfig(request as never);
    await listRiskCells(request as never, { window: "24h" });
    await getRiskCellsGeoJSON(request as never, { resolution: 9 });
    await getRiskSummary(request as never, { window: "7d" });
    await getRiskCell(request as never, "cell-1", { resolution: 8, window: "7d" });
    await getRiskTrends(request as never, { window: "30d" });
    await getRiskInfrastructureExposure(request as never, { resolution: 7 });

    expect(request.mock.calls[0]?.[0]).toBe("/api/v1/risk/config");
    expect(request.mock.calls[1]?.[0]).toContain("/api/v1/risk/cells?");
    expect(request.mock.calls[2]?.[0]).toContain("format=geojson");
    expect(request.mock.calls[3]?.[0]).toContain("/api/v1/risk/summary?");
    expect(request.mock.calls[4]?.[0]).toContain(
      "/api/v1/risk/cells/cell-1?",
    );
    expect(request.mock.calls[5]?.[0]).toContain("/api/v1/risk/trends?");
    expect(request.mock.calls[6]?.[0]).toContain(
      "/api/v1/risk/infrastructure-exposure?",
    );
  });
});
