import { describe, expect, it } from "vitest";

import { parseCoordinates } from "@/lib/location";

describe("incident coordinate parsing", () => {
  it("rejects empty coordinates instead of filing at zero", () => {
    const result = parseCoordinates("", "");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("Place a pin");
    }
    expect(parseCoordinates(" ", "90.4").ok).toBe(false);
    expect(parseCoordinates("23.8", "").ok).toBe(false);
  });

  it("accepts valid WGS84 coordinates", () => {
    expect(parseCoordinates("23.790000", "90.400000")).toEqual({
      ok: true,
      latitude: 23.79,
      longitude: 90.4,
    });
    expect(parseCoordinates("0", "0").ok).toBe(true);
    expect(parseCoordinates("-90", "-180").ok).toBe(true);
  });

  it("rejects out-of-range and non-numeric values", () => {
    const invalid: Array<[string, string]> = [
      ["91", "0"],
      ["-91", "0"],
      ["0", "181"],
      ["0", "-181"],
      ["abc", "90"],
      ["23.8", "xyz"],
    ];
    for (const [latitude, longitude] of invalid) {
      expect(parseCoordinates(latitude, longitude).ok).toBe(false);
    }
  });
});
