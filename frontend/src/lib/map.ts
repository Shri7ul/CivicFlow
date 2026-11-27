import type { Feature, FeatureCollection, Point } from "geojson";
import type {
  Map as MapLibreMap,
  RasterTileSource,
} from "maplibre-gl";

import {
  DEFAULT_GEOGRAPHIC_CONTEXT,
  mapViewForContext,
} from "@/config/geography";
import { categoryLabels } from "@/lib/incidents";
import type { Incident, IncidentCategory } from "@/types/incidents";

export const DEFAULT_MAP_VIEW = mapViewForContext(
  DEFAULT_GEOGRAPHIC_CONTEXT,
) as {
  longitude: number;
  latitude: number;
  zoom: number;
};

export const MIN_MAP_ZOOM = 8;
export const MAX_MAP_ZOOM = 19;

// tile.openstreetmap.org serves a rendered "Access blocked" image with HTTP
// 200, and CARTO's hosted raster tiles can serve an "API KEY REQUIRED"
// watermark with HTTP 200. MapLibre treats both as successful images, so an
// error-based fallback never fires. Esri World Dark Gray Base is therefore the
// primary source: key-free, dark, and clean in production.
export const BASEMAP_TILES = [
  "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
];
// Kept as an alias for callers that import the old name.
export const OSM_TILES = BASEMAP_TILES;
// Automatic fallback on a different Esri host. Standard non-retina CARTO
// tiles were tested too, but they also serve an "API KEY REQUIRED" watermark
// with HTTP 200, so they cannot satisfy a zero-watermark requirement.
export const FALLBACK_TILES = [
  "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
];
const MAP_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · © <a href="https://carto.com/attributions">CARTO</a> · Tiles © <a href="https://www.esri.com/">Esri</a>';

export const OSM_STYLE = {
  version: 8 as const,
  glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
  sources: {
    osm: {
      type: "raster" as const,
      tiles: BASEMAP_TILES,
      tileSize: 256,
      attribution: MAP_ATTRIBUTION,
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

/** True for raster tile/network errors that the fallback source can repair. */
export function isTileLoadError(message: string | undefined): boolean {
  if (!message) return false;
  return /tile|raster|image|failed to fetch|status code|404|403|429/i.test(message);
}

/**
 * Swap the raster source to a fallback basemap once if tile loading fails.
 * Returns an unsubscribe function. It never retries in a loop or reloads the
 * page, and it keeps the app usable with coordinate inputs if both fail.
 */
export function installRasterTileFallback(
  map: MapLibreMap,
  onFallback?: () => void,
): () => void {
  let swapped = false;
  const handler = (event: { error?: Error }) => {
    if (swapped || !isTileLoadError(event.error?.message)) return;
    const source = map.getSource("osm") as RasterTileSource | undefined;
    if (!source || typeof source.setTiles !== "function") return;
    swapped = true;
    source.setTiles(FALLBACK_TILES);
    onFallback?.();
  };
  map.on("error", handler);
  return () => map.off("error", handler);
}

export const CATEGORY_SHORT: Record<IncidentCategory, string> = {
  ROADS: "RD",
  DRAINAGE: "DR",
  SANITATION: "SA",
  UTILITIES: "UT",
  PUBLIC_SAFETY: "PS",
  HEALTH: "HL",
  ENVIRONMENT: "EN",
  OTHER: "OT",
};

export type IncidentFeatureProperties = {
  id: string;
  title: string;
  category: IncidentCategory;
  categoryLabel: string;
  categoryShort: string;
  severity: Incident["severity"];
  status: Incident["status"];
};

export type IncidentFeatureCollection = FeatureCollection<
  Point,
  IncidentFeatureProperties
>;

export function incidentToFeature(
  incident: Incident,
): Feature<Point, IncidentFeatureProperties> {
  return {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [incident.longitude, incident.latitude],
    },
    properties: {
      id: incident.id,
      title: incident.title,
      category: incident.category,
      categoryLabel: categoryLabels[incident.category],
      categoryShort: CATEGORY_SHORT[incident.category],
      severity: incident.severity,
      status: incident.status,
    },
  };
}

export function incidentsToGeoJSON(
  incidents: readonly Incident[],
): IncidentFeatureCollection {
  return {
    type: "FeatureCollection",
    features: incidents.map(incidentToFeature),
  };
}

export function selectedIncidentGeoJSON(
  incident: Incident | null,
): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features: incident
      ? [
          {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: [incident.longitude, incident.latitude],
            },
            properties: {},
          },
        ]
      : [],
  };
}
