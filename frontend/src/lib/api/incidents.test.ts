import { describe, expect, it } from "vitest";

import { buildIncidentQuery } from "@/lib/api/incidents";

describe("buildIncidentQuery", () => {
  it("includes pagination defaults", () => {
    expect(buildIncidentQuery()).toBe("page=1&page_size=20");
  });

  it("serializes filters and trims search text", () => {
    const query = buildIncidentQuery({
      page: 2,
      pageSize: 12,
      status: "OPEN",
      category: "DRAINAGE",
      severity: "HIGH",
      query: "  storm drain  ",
    });
    const params = new URLSearchParams(query);

    expect(params.get("page")).toBe("2");
    expect(params.get("page_size")).toBe("12");
    expect(params.get("status")).toBe("OPEN");
    expect(params.get("category")).toBe("DRAINAGE");
    expect(params.get("severity")).toBe("HIGH");
    expect(params.get("q")).toBe("storm drain");
  });

  it("omits empty filters", () => {
    const params = new URLSearchParams(
      buildIncidentQuery({ status: "", category: "", query: "   " }),
    );

    expect(params.has("status")).toBe(false);
    expect(params.has("category")).toBe(false);
    expect(params.has("q")).toBe(false);
  });

  it("serializes department and viewport bounds", () => {
    const params = new URLSearchParams(
      buildIncidentQuery({
        departmentId: "dept-1",
        minLatitude: 23.7,
        minLongitude: 90.3,
        maxLatitude: 23.9,
        maxLongitude: 90.5,
      }),
    );

    expect(params.get("department_id")).toBe("dept-1");
    expect(params.get("min_latitude")).toBe("23.7");
    expect(params.get("min_longitude")).toBe("90.3");
    expect(params.get("max_latitude")).toBe("23.9");
    expect(params.get("max_longitude")).toBe("90.5");
  });

  it("does not send an incomplete or inverted viewport", () => {
    const partial = new URLSearchParams(
      buildIncidentQuery({ minLatitude: 23.7, maxLatitude: 23.9 }),
    );
    expect(partial.has("min_latitude")).toBe(false);

    const inverted = new URLSearchParams(
      buildIncidentQuery({
        minLatitude: 24,
        minLongitude: 90.5,
        maxLatitude: 23,
        maxLongitude: 90.3,
      }),
    );
    expect(inverted.has("min_latitude")).toBe(false);
  });
});
