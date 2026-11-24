/**
 * Central geographic identity configuration.
 *
 * These values mirror the authoritative backend registry in
 * `app/geo/contexts.py`. The API remains the source of truth at runtime; this
 * module exists so map defaults and labels cannot be arbitrary hardcoded
 * strings. A context is an identity, not proof of operational status.
 */

export type GeographicContextKey = "BD-DHAKA" | "US-NYC";

export interface GeographicContextConfig {
  readonly key: GeographicContextKey;
  readonly displayName: string;
  readonly countryCode: string;
  readonly bboxGeoJson: readonly [number, number, number, number];
  readonly center: Readonly<{ latitude: number; longitude: number }>;
  readonly boundaryStatus: string;
  readonly isPilotEligible: boolean;
  readonly researchOnly: boolean;
  readonly note: string;
}

export const GEOGRAPHIC_CONTEXTS: readonly GeographicContextConfig[] = [
  {
    key: "BD-DHAKA",
    displayName: "Dhaka, Bangladesh (research / pilot candidate)",
    countryCode: "BD",
    bboxGeoJson: [90.3, 23.68, 90.5, 23.9],
    center: { latitude: 23.8103, longitude: 90.4125 },
    boundaryStatus: "BLOCKED",
    isPilotEligible: false,
    researchOnly: true,
    note: "No approved pilot area or authoritative DNCC/DSCC boundary.",
  },
  {
    key: "US-NYC",
    displayName: "New York City (historical research)",
    countryCode: "US",
    bboxGeoJson: [-74.3, 40.4, -73.6, 41.0],
    center: { latitude: 40.72, longitude: -73.98 },
    boundaryStatus: "NOT_ASSESSED",
    isPilotEligible: false,
    researchOnly: true,
    note: "Historical validation only; never Dhaka operational evidence.",
  },
] as const;

export const DEFAULT_GEOGRAPHIC_CONTEXT: GeographicContextKey = "BD-DHAKA";

export function geographicContextConfig(
  key: string,
): GeographicContextConfig | undefined {
  return GEOGRAPHIC_CONTEXTS.find((item) => item.key === key);
}

export function mapViewForContext(key: string): {
  longitude: number;
  latitude: number;
  zoom: number;
} {
  const config = geographicContextConfig(key) ?? GEOGRAPHIC_CONTEXTS[0]!;
  return {
    longitude: config.center.longitude,
    latitude: config.center.latitude,
    zoom: config.key === "BD-DHAKA" ? 11.5 : 10.5,
  };
}

export function isRegisteredGeographicContext(key: string): boolean {
  return geographicContextConfig(key) !== undefined;
}
