import type { Feature, FeatureCollection, Point } from "geojson";

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
export const OSM_STYLE = {
  version: 8 as const,
  glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

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
