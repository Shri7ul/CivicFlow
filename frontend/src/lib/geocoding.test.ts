import { afterEach, describe, expect, it, vi } from "vitest";

import { reverseGeocode } from "@/lib/geocoding";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("reverseGeocode", () => {
  it("builds a readable label from address components", async () => {
    const fetchMock = vi.fn(async (_url: URL | string, _init?: RequestInit) => ({
      ok: true,
      json: async () => ({
        display_name: "Road 12, Dhanmondi, Dhaka",
        address: {
          road: "Road 12",
          neighbourhood: "Dhanmondi",
          city: "Dhaka",
        },
      }),
    }));
    vi.stubGlobal("fetch", fetchMock);
    const label = await reverseGeocode(23.81031, 90.41252);
    expect(label).toBe("Road 12, Dhanmondi, Dhaka");
    const url = String(fetchMock.mock.calls[0]![0]);
    expect(url).toContain("nominatim.openstreetmap.org/reverse");
    expect(url).toContain("lat=23.81031");
    expect(url).toContain("lon=90.41252");
  });

  it("returns null instead of inventing an address when the service fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, json: async () => ({}) })),
    );
    expect(await reverseGeocode(11.11111, 22.22222)).toBeNull();
  });
});
