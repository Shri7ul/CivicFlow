/**
 * Shared coordinate parsing for user-entered incident locations.
 * An empty value is never coerced to zero: that would file a report at a
 * fabricated location the user never selected.
 */
export type CoordinatesResult =
  | { ok: true; latitude: number; longitude: number }
  | { ok: false; message: string };

export function parseCoordinates(
  latitude: string,
  longitude: string,
): CoordinatesResult {
  if (latitude.trim() === "" || longitude.trim() === "") {
    return {
      ok: false,
      message:
        "Place a pin on the map, use your current location, or enter coordinates.",
    };
  }
  const parsedLatitude = Number(latitude);
  const parsedLongitude = Number(longitude);
  if (!Number.isFinite(parsedLatitude) || parsedLatitude < -90 || parsedLatitude > 90) {
    return { ok: false, message: "Latitude must be between -90 and 90." };
  }
  if (
    !Number.isFinite(parsedLongitude) ||
    parsedLongitude < -180 ||
    parsedLongitude > 180
  ) {
    return { ok: false, message: "Longitude must be between -180 and 180." };
  }
  return {
    ok: true,
    latitude: parsedLatitude,
    longitude: parsedLongitude,
  };
}
