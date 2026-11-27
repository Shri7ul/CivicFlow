/**
 * Best-effort reverse geocoding for the location picker.
 *
 * Uses Nominatim's public API (no key). A failure simply leaves the exact
 * coordinates visible; no address is ever guessed or fabricated.
 */

const cache = new Map<string, string | null>();

function keyOf(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)},${longitude.toFixed(4)}`;
}

export async function reverseGeocode(
  latitude: number,
  longitude: number,
  signal?: AbortSignal,
): Promise<string | null> {
  const key = keyOf(latitude, longitude);
  if (cache.has(key)) {
    return cache.get(key) ?? null;
  }

  const url = new URL("https://nominatim.openstreetmap.org/reverse");
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("lat", String(latitude));
  url.searchParams.set("lon", String(longitude));
  url.searchParams.set("zoom", "18");
  url.searchParams.set("addressdetails", "1");
  url.searchParams.set("accept-language", "en");

  try {
    const response = await fetch(url, {
      signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== "object") {
      return null;
    }
    const record = payload as {
      display_name?: unknown;
      address?: Record<string, unknown>;
    };
    const address = record.address ?? {};
    const parts: string[] = [];
    for (const field of [
      "road",
      "neighbourhood",
      "suburb",
      "city_district",
      "quarter",
      "town",
      "city",
      "village",
      "county",
      "state_district",
      "state",
    ]) {
      const value = address[field];
      if (typeof value === "string" && value.trim() && !parts.includes(value.trim())) {
        parts.push(value.trim());
      }
      if (parts.length >= 4) break;
    }
    const label =
      parts.length > 0
        ? parts.join(", ")
        : typeof record.display_name === "string"
          ? record.display_name
          : null;
    cache.set(key, label);
    return label;
  } catch {
    // Do not cache transient failures; a later request may succeed.
    return null;
  }
}
