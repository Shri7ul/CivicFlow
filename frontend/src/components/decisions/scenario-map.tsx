"use client";

import { useEffect, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

import { useAuth } from "@/components/auth/auth-provider";
import { getRiskCellsGeoJSON } from "@/lib/api/risk";
import { DEFAULT_MAP_VIEW, OSM_STYLE } from "@/lib/map";
import type { RiskGeoJSON } from "@/types/risk";

type Props = {
  targetCells: string[];
  resolution?: number;
};

const EMPTY = {
  type: "FeatureCollection",
  features: [],
} as unknown as RiskGeoJSON;

export function ScenarioMap({ targetCells, resolution = 8 }: Props) {
  const { apiRequest } = useAuth();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [features, setFeatures] = useState<RiskGeoJSON>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let map: MapLibreMap | null = null;
    let resizeObserver: ResizeObserver | null = null;
    void (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (disposed || !containerRef.current) return;
        map = new maplibre.Map({
          container: containerRef.current,
          style: OSM_STYLE as StyleSpecification,
          center: [DEFAULT_MAP_VIEW.longitude, DEFAULT_MAP_VIEW.latitude],
          zoom: DEFAULT_MAP_VIEW.zoom,
          minZoom: 7,
          maxZoom: 19,
          attributionControl: false,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(new maplibre.AttributionControl({ compact: true }), "bottom-right");
        map.on("load", () => {
          if (disposed || !map) return;
          map.addSource("scenario-targets", { type: "geojson", data: EMPTY });
          map.addLayer({
            id: "scenario-targets-fill",
            type: "fill",
            source: "scenario-targets",
            paint: { "fill-color": "#34d399", "fill-opacity": 0.28 },
          });
          map.addLayer({
            id: "scenario-targets-line",
            type: "line",
            source: "scenario-targets",
            paint: { "line-color": "#6ee7b7", "line-width": 2 },
          });
          map.addLayer({
            id: "scenario-targets-labels",
            type: "symbol",
            source: "scenario-targets",
            layout: {
              "text-field": ["get", "risk_score"],
              "text-size": 11,
              "text-font": ["Open Sans Regular"],
            },
            paint: {
              "text-color": "#f8fafc",
              "text-halo-color": "#020617",
              "text-halo-width": 1.2,
            },
          });
          map.resize();
          setMapReady(true);
        });
        map.on("error", (event) => {
          if (!disposed) setError(event.error?.message ?? "Map rendering failed.");
        });
        resizeObserver = new ResizeObserver(() => {
          if (!disposed) map?.resize();
        });
        resizeObserver.observe(containerRef.current);
      } catch (loadError) {
        if (!disposed) {
          setError(loadError instanceof Error ? loadError.message : "Map failed.");
        }
      }
    })();
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    const targets = new Set(targetCells);
    void getRiskCellsGeoJSON(apiRequest, { resolution, limit: 500 })
      .then((data) => {
        if (disposed) return;
        const filtered = {
          ...data,
          features: data.features.filter((feature) => {
            const cell = feature.properties?.h3_cell_id;
            return typeof cell === "string" && targets.has(cell);
          }),
        } as RiskGeoJSON;
        setFeatures(filtered);
        setError(null);
      })
      .catch((loadError) => {
        if (!disposed) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load risk cells.");
        }
      });
    return () => {
      disposed = true;
    };
  }, [apiRequest, resolution, targetCells]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    const source = map.getSource("scenario-targets") as GeoJSONSource | undefined;
    source?.setData(features as never);
    if (features.features.length > 0) {
      const coordinates = features.features.flatMap((feature) => {
        const geometry = feature.geometry;
        if (geometry.type !== "Polygon") return [];
        return geometry.coordinates[0] ?? [];
      });
      if (coordinates.length > 0) {
        const lngs = coordinates.map((position) => position[0] as number);
        const lats = coordinates.map((position) => position[1] as number);
        map.fitBounds(
          [
            [Math.min(...lngs), Math.min(...lats)],
            [Math.max(...lngs), Math.max(...lats)],
          ],
          { padding: 48, maxZoom: 13, duration: 0 },
        );
      }
    }
  }, [features, mapReady]);

  return (
    <div className="relative h-[340px] w-full overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
      <div ref={containerRef} className="h-[340px] w-full" />
      <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-white/10 bg-slate-950/85 px-3 py-2 text-[11px] text-slate-300">
        {targetCells.length} target H3 cell{targetCells.length === 1 ? "" : "s"} · planning overlay
      </div>
      {error ? (
        <p className="absolute bottom-3 left-3 right-3 rounded-lg border border-rose-300/25 bg-rose-300/10 p-2 text-xs text-rose-200">
          {error}
        </p>
      ) : null}
      {!error && targetCells.length === 0 ? (
        <p className="absolute inset-x-3 bottom-3 rounded-lg border border-white/10 bg-slate-950/85 p-2 text-xs text-slate-400">
          Add an action with a target H3 cell to preview it here.
        </p>
      ) : null}
    </div>
  );
}
