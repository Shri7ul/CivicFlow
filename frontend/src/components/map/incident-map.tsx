"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";

import { useAuth } from "@/components/auth/auth-provider";
import { SeverityBadge, StatusBadge } from "@/components/incidents/status-badge";
import { listDepartments, listIncidents } from "@/lib/api/incidents";
import {
  categories,
  categoryLabels,
  formatCoordinates,
  formatDateTime,
  severities,
  severityLabels,
  statuses,
  statusLabels,
} from "@/lib/incidents";
import {
  DEFAULT_MAP_VIEW,
  incidentsToGeoJSON,
  installRasterTileFallback,
  isTileLoadError,
  MAX_MAP_ZOOM,
  MIN_MAP_ZOOM,
  OSM_STYLE,
  selectedIncidentGeoJSON,
} from "@/lib/map";
import type {
  Department,
  Incident,
  IncidentCategory,
  IncidentList,
  IncidentSeverity,
  IncidentStatus,
} from "@/types/incidents";

const PAGE_SIZE = 100;
const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};

const selectClass =
  "min-w-0 rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-emerald-400/50";

type Viewport = {
  minLatitude: number;
  minLongitude: number;
  maxLatitude: number;
  maxLongitude: number;
};

function viewportFromMap(map: MapLibreMap): Viewport {
  const bounds = map.getBounds();
  return {
    minLatitude: bounds.getSouth(),
    minLongitude: bounds.getWest(),
    maxLatitude: bounds.getNorth(),
    maxLongitude: bounds.getEast(),
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Unable to load map incidents.";
}

/** Build popup DOM with textContent only, so incident text can never inject HTML. */
function buildPopupContent(incident: Incident): HTMLDivElement {
  const root = document.createElement("div");
  root.style.cssText =
    "min-width:220px;max-width:300px;color:#e2e8f0;font-size:12px;line-height:1.5";

  const title = document.createElement("div");
  title.style.cssText = "font-weight:600;font-size:13px;color:#fff;margin-bottom:6px";
  title.textContent = incident.title;
  root.appendChild(title);

  const chips = document.createElement("div");
  chips.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px";
  for (const [label, value, color] of [
    ["Severity", severityLabels[incident.severity], "#fbbf24"],
    ["Status", statusLabels[incident.status], "#34d399"],
  ] as const) {
    const chip = document.createElement("span");
    chip.style.cssText = `border:1px solid ${color}55;border-radius:9999px;padding:1px 8px;color:${color}`;
    chip.textContent = `${label}: ${value}`;
    chips.appendChild(chip);
  }
  root.appendChild(chips);

  const address = document.createElement("div");
  address.style.cssText = "color:#94a3b8";
  address.textContent = incident.address?.trim()
    ? incident.address
    : "No address supplied";
  root.appendChild(address);

  const coordinates = document.createElement("div");
  coordinates.style.cssText = "color:#64748b;margin-top:2px";
  coordinates.textContent = formatCoordinates(incident.latitude, incident.longitude);
  root.appendChild(coordinates);

  return root;
}

function addMapLayers(map: MapLibreMap) {
  map.addLayer({
    id: "incident-clusters",
    type: "circle",
    source: "incidents",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": [
        "step",
        ["get", "point_count"],
        "#34d399",
        10,
        "#38bdf8",
        50,
        "#a78bfa",
      ],
      "circle-radius": [
        "step",
        ["get", "point_count"],
        17,
        10,
        23,
        50,
        30,
      ],
      "circle-stroke-color": "#f8fafc",
      "circle-stroke-width": 2,
      "circle-opacity": 0.92,
    },
  });
  map.addLayer({
    id: "incident-cluster-count",
    type: "symbol",
    source: "incidents",
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-size": 11,
      "text-font": ["Open Sans Regular"],
    },
    paint: {
      "text-color": "#020617",
    },
  });
  map.addLayer({
    id: "incident-points",
    type: "circle",
    source: "incidents",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "match",
        ["get", "severity"],
        "CRITICAL",
        "#fb7185",
        "HIGH",
        "#fbbf24",
        "MEDIUM",
        "#38bdf8",
        "LOW",
        "#94a3b8",
        "#94a3b8",
      ],
      "circle-radius": [
        "match",
        ["get", "severity"],
        "CRITICAL",
        11,
        "HIGH",
        10,
        "MEDIUM",
        9,
        "LOW",
        8,
        8,
      ],
      "circle-stroke-color": [
        "match",
        ["get", "status"],
        "CLOSED",
        "#94a3b8",
        "RESOLVED",
        "#34d399",
        "IN_PROGRESS",
        "#a78bfa",
        "ACKNOWLEDGED",
        "#38bdf8",
        "OPEN",
        "#fbbf24",
        "#f8fafc",
      ],
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "incident-category-labels",
    type: "symbol",
    source: "incidents",
    filter: ["!", ["has", "point_count"]],
    layout: {
      "text-field": ["get", "categoryShort"],
      "text-size": 7,
      "text-font": ["Open Sans Regular"],
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": "#020617",
    },
  });
  map.addLayer({
    id: "incident-selected-ring",
    type: "circle",
    source: "selected-incident",
    paint: {
      "circle-color": "rgba(0, 0, 0, 0)",
      "circle-radius": 17,
      "circle-stroke-color": "#f8fafc",
      "circle-stroke-width": 3,
    },
  });
}

export function IncidentMapView() {
  const { apiRequest } = useAuth();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const maplibreRef = useRef<typeof import("maplibre-gl") | null>(null);
  const userMarkerRef = useRef<import("maplibre-gl").Marker | null>(null);
  const popupRef = useRef<import("maplibre-gl").Popup | null>(null);
  const incidentsRef = useRef<Incident[]>([]);
  const requestIdRef = useRef(0);

  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [data, setData] = useState<IncidentList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [category, setCategory] = useState<IncidentCategory | "">("");
  const [severity, setSeverity] = useState<IncidentSeverity | "">("");
  const [departmentId, setDepartmentId] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);

  const incidents = useMemo(() => data?.items ?? [], [data]);

  useEffect(() => {
    incidentsRef.current = incidents;
  }, [incidents]);

  const selectedIncident =
    incidents.find((incident) => incident.id === selectedId) ?? null;
  const hasFilters = Boolean(
    query.trim() || status || category || severity || departmentId,
  );

  useEffect(() => {
    let disposed = false;
    let map: MapLibreMap | null = null;
    let removeTileFallback: (() => void) | null = null;

    void (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (disposed || !containerRef.current) {
          return;
        }
        maplibreRef.current = maplibre;
        map = new maplibre.Map({
          container: containerRef.current,
          style: OSM_STYLE as StyleSpecification,
          center: [DEFAULT_MAP_VIEW.longitude, DEFAULT_MAP_VIEW.latitude],
          zoom: DEFAULT_MAP_VIEW.zoom,
          minZoom: MIN_MAP_ZOOM,
          maxZoom: MAX_MAP_ZOOM,
          attributionControl: false,
        });
        mapRef.current = map;
        removeTileFallback = installRasterTileFallback(map, () =>
          setMapError(null),
        );
        map.on("error", (event) => {
          if (disposed || isTileLoadError(event.error?.message)) return;
          setMapError(event.error?.message ?? "Map rendering failed.");
        });
        if (process.env.NODE_ENV !== "production") {
          (
            window as Window & { __civicflowMap?: MapLibreMap }
          ).__civicflowMap = map;
        }
        map.addControl(
          new maplibre.NavigationControl({ showCompass: false }),
          "top-right",
        );
        map.addControl(
          new maplibre.AttributionControl({ compact: true }),
          "bottom-right",
        );

        map.on("load", () => {
          if (disposed || !map) {
            return;
          }
          map.addSource("incidents", {
            type: "geojson",
            data: EMPTY_COLLECTION,
            cluster: true,
            clusterMaxZoom: 15,
            clusterRadius: 48,
          });
          map.addSource("selected-incident", {
            type: "geojson",
            data: EMPTY_COLLECTION,
          });
          addMapLayers(map);
          setMapReady(true);
          setViewport(viewportFromMap(map));
        });

        map.on("moveend", () => {
          if (!disposed && map) {
            setViewport(viewportFromMap(map));
          }
        });

        map.on("click", "incident-clusters", (event) => {
          const feature = event.features?.[0];
          if (!feature || !map) {
            return;
          }
          const clusterId = Number(feature.properties?.cluster_id);
          const source = map.getSource("incidents") as GeoJSONSource;
          if (feature.geometry.type !== "Point") {
            return;
          }
          const coordinates = feature.geometry.coordinates as [number, number];
          source.getClusterExpansionZoom(clusterId).then((zoom) => {
            map?.easeTo({ center: coordinates, zoom });
          });
        });

        map.on("click", "incident-points", (event) => {
          const feature = event.features?.[0];
          const incidentId = feature?.properties?.id;
          if (typeof incidentId !== "string") {
            return;
          }
          setSelectedId(incidentId);
          const incident = incidentsRef.current.find(
            (item) => item.id === incidentId,
          );
          const maplibre = maplibreRef.current;
          if (!incident || !maplibre || !map) {
            return;
          }
          popupRef.current?.remove();
          popupRef.current = new maplibre.Popup({
            closeButton: true,
            maxWidth: "320px",
            offset: 14,
          })
            .setLngLat([incident.longitude, incident.latitude])
            .setDOMContent(buildPopupContent(incident))
            .addTo(map);
        });

        map.on("click", (event) => {
          if (!map) {
            return;
          }
          const features = map.queryRenderedFeatures(event.point, {
            layers: ["incident-points", "incident-clusters"],
          });
          if (features.length === 0) {
            setSelectedId(null);
            popupRef.current?.remove();
            popupRef.current = null;
          }
        });

        for (const layer of ["incident-clusters", "incident-points"]) {
          map.on("mouseenter", layer, () => {
            if (map) map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            if (map) map.getCanvas().style.cursor = "";
          });
        }
      } catch (loadError) {
        if (!disposed) {
          setMapError(errorMessage(loadError));
        }
      }
    })();

    return () => {
      disposed = true;
      removeTileFallback?.();
      if (process.env.NODE_ENV !== "production") {
        delete (window as Window & { __civicflowMap?: MapLibreMap })
          .__civicflowMap;
      }
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      popupRef.current?.remove();
      popupRef.current = null;
      mapRef.current = null;
      maplibreRef.current = null;
      map?.remove();
    };
  }, []);

  useEffect(() => {
    const source = mapRef.current?.getSource("incidents") as
      | GeoJSONSource
      | undefined;
    if (source && mapReady) {
      source.setData(incidentsToGeoJSON(incidents));
    }
  }, [incidents, mapReady]);

  useEffect(() => {
    const source = mapRef.current?.getSource("selected-incident") as
      | GeoJSONSource
      | undefined;
    if (source && mapReady) {
      source.setData(selectedIncidentGeoJSON(selectedIncident));
    }
  }, [mapReady, selectedIncident]);

  useEffect(() => {
    void listDepartments(apiRequest)
      .then(setDepartments)
      .catch(() => setDepartments([]));
  }, [apiRequest]);

  useEffect(() => {
    if (!mapReady || !viewport) {
      return;
    }
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      void listIncidents(
        apiRequest,
        {
          page: 1,
          pageSize: PAGE_SIZE,
          status,
          category,
          severity,
          departmentId,
          query,
          ...viewport,
        },
        { signal: controller.signal },
      )
        .then((next) => {
          if (requestId === requestIdRef.current) {
            setData(next);
          }
        })
        .catch((loadError: unknown) => {
          if (
            requestId === requestIdRef.current &&
            !(
              loadError instanceof Error &&
              "code" in loadError &&
              loadError.code === "request_cancelled"
            )
          ) {
            setError(errorMessage(loadError));
          }
        })
        .finally(() => {
          if (requestId === requestIdRef.current) {
            setLoading(false);
          }
        });
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    apiRequest,
    category,
    departmentId,
    mapReady,
    query,
    reloadKey,
    severity,
    status,
    viewport,
  ]);

  const resetFilters = useCallback(() => {
    setQuery("");
    setStatus("");
    setCategory("");
    setSeverity("");
    setDepartmentId("");
    setSelectedId(null);
  }, []);

  function focusIncident(incident: Incident) {
    setSelectedId(incident.id);
    mapRef.current?.flyTo({
      center: [incident.longitude, incident.latitude],
      zoom: Math.max(14, mapRef.current.getZoom()),
    });
  }

  function resetViewport() {
    mapRef.current?.flyTo({
      center: [DEFAULT_MAP_VIEW.longitude, DEFAULT_MAP_VIEW.latitude],
      zoom: DEFAULT_MAP_VIEW.zoom,
    });
  }

  function locateMe() {
    if (!navigator.geolocation) {
      setLocationError("Geolocation is not available in this browser.");
      return;
    }
    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        mapRef.current?.flyTo({ center: [longitude, latitude], zoom: 14 });
        if (maplibreRef.current && mapRef.current) {
          userMarkerRef.current?.remove();
          userMarkerRef.current = new maplibreRef.current.Marker({
            color: "#38bdf8",
          })
            .setLngLat([longitude, latitude])
            .addTo(mapRef.current);
        }
        setLocating(false);
      },
      (positionError) => {
        setLocationError(
          positionError.code === positionError.PERMISSION_DENIED
            ? "Location permission was denied. You can still explore the map."
            : positionError.code === positionError.TIMEOUT
              ? "Location lookup timed out. Try again or pan to your area."
              : "Your location is unavailable. You can still explore the map.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  const resultLabel = useMemo(() => {
    if (loading) {
      return "Loading incidents in this viewport…";
    }
    if (!data) {
      return "Move the map to load incidents.";
    }
    return `${data.total} incident${data.total === 1 ? "" : "s"} in this area`;
  }, [data, loading]);

  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Spatial operations
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Incident map
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            Explore reports in the current viewport. Pan or zoom to query the
            API again; markers cluster as you zoom out. Dhaka is a research
            context, not an active operational pilot.
          </p>
        </div>
        <Link
          href="/incidents"
          className="rounded-xl border border-white/15 px-4 py-2.5 text-sm font-medium text-white transition hover:border-white/25"
        >
          Open list view
        </Link>
      </div>

      <section
        aria-label="Map filters"
        className="mt-7 rounded-2xl border border-white/10 bg-white/[0.03] p-4"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search reports"
            aria-label="Search map incidents"
            className={`${selectClass} w-full lg:col-span-2`}
          />
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as IncidentStatus | "")
            }
            aria-label="Filter map by status"
            className={selectClass}
          >
            <option value="">All statuses</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {statusLabels[value]}
              </option>
            ))}
          </select>
          <select
            value={severity}
            onChange={(event) =>
              setSeverity(event.target.value as IncidentSeverity | "")
            }
            aria-label="Filter map by severity"
            className={selectClass}
          >
            <option value="">All severities</option>
            {severities.map((value) => (
              <option key={value} value={value}>
                {severityLabels[value]}
              </option>
            ))}
          </select>
          <select
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as IncidentCategory | "")
            }
            aria-label="Filter map by category"
            className={selectClass}
          >
            <option value="">All categories</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabels[value]}
              </option>
            ))}
          </select>
          <select
            value={departmentId}
            onChange={(event) => setDepartmentId(event.target.value)}
            aria-label="Filter map by department"
            className={selectClass}
          >
            <option value="">All departments</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[11px] text-slate-500" role="status">
            {resultLabel}
            {data && data.total > data.items.length
              ? ` · showing first ${data.items.length}`
              : ""}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={resetFilters}
              disabled={!hasFilters}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-40"
            >
              Reset filters
            </button>
            <button
              type="button"
              onClick={resetViewport}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300"
            >
              Reset viewport
            </button>
            <button
              type="button"
              onClick={locateMe}
              disabled={locating}
              className="rounded-lg bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
            >
              {locating ? "Locating…" : "Use my location"}
            </button>
          </div>
        </div>
        {locationError ? (
          <p role="alert" className="mt-2 text-xs text-amber-200">
            {locationError}
          </p>
        ) : null}
      </section>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1.55fr_0.45fr]">
        <section
          className="relative min-h-[420px] overflow-hidden rounded-3xl border border-white/10 bg-slate-950"
          aria-label="Interactive incident map"
        >
          <div ref={containerRef} className="h-[520px] w-full" />
          {!mapReady && !mapError ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/70">
              <p className="text-sm text-slate-300">Loading map…</p>
            </div>
          ) : null}
          {mapError ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-950/95 p-6 text-center">
              <div>
                <p className="text-sm text-rose-200">{mapError}</p>
                <button
                  type="button"
                  onClick={() => {
                    setMapError(null);
                    mapRef.current?.resize();
                    mapRef.current?.triggerRepaint();
                  }}
                  className="mt-4 rounded-lg border border-white/15 px-4 py-2 text-sm text-white"
                >
                  Retry map
                </button>
              </div>
            </div>
          ) : null}
          <div className="pointer-events-none absolute left-4 top-4 rounded-xl border border-white/10 bg-slate-950/85 px-3 py-2 text-[11px] text-slate-300 shadow-lg">
            <p className="font-semibold text-white">Legend</p>
            <p className="mt-1">Fill: severity · Ring: status · Label: category</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1">
                <i className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                Critical
              </span>
              <span className="inline-flex items-center gap-1">
                <i className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                High
              </span>
              <span className="inline-flex items-center gap-1">
                <i className="h-2.5 w-2.5 rounded-full bg-sky-400" />
                Medium
              </span>
              <span className="inline-flex items-center gap-1">
                <i className="h-2.5 w-2.5 rounded-full bg-slate-400" />
                Low
              </span>
            </div>
          </div>
          {error ? (
            <div className="absolute inset-x-4 bottom-4 rounded-xl border border-rose-300/20 bg-rose-950/95 p-3 text-xs text-rose-100">
              {error}
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setReloadKey((value) => value + 1);
                }}
                className="ml-3 rounded border border-white/20 px-2 py-1 font-semibold"
              >
                Retry
              </button>
            </div>
          ) : null}
        </section>

        <aside className="min-w-0 space-y-4">
          {selectedIncident ? (
            <section className="rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.06] p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex flex-wrap gap-1.5">
                  <StatusBadge status={selectedIncident.status} />
                  <SeverityBadge severity={selectedIncident.severity} />
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  aria-label="Clear selected incident"
                  className="rounded p-1 text-slate-400 hover:text-white"
                >
                  ×
                </button>
              </div>
              <h2 className="mt-3 text-sm font-semibold text-white">
                {selectedIncident.title}
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                {categoryLabels[selectedIncident.category]} ·{" "}
                {formatCoordinates(
                  selectedIncident.latitude,
                  selectedIncident.longitude,
                )}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Updated {formatDateTime(selectedIncident.updated_at)}
              </p>
              <Link
                href={`/incidents/${selectedIncident.id}`}
                className="mt-3 inline-flex rounded-lg bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950"
              >
                Open incident detail
              </Link>
            </section>
          ) : null}

          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">In this view</h2>
              <span className="text-[11px] text-slate-500">
                {incidents.length}
              </span>
            </div>
            {incidents.length === 0 ? (
              <p className="mt-3 text-xs leading-5 text-slate-500">
                {loading
                  ? "Loading reports…"
                  : "No reports match the current viewport and filters."}
              </p>
            ) : (
              <ul className="mt-3 max-h-[430px] space-y-2 overflow-y-auto pr-1">
                {incidents.map((incident) => (
                  <li key={incident.id}>
                    <button
                      type="button"
                      onClick={() => focusIncident(incident)}
                      className={`w-full rounded-xl border p-3 text-left transition ${
                        incident.id === selectedId
                          ? "border-emerald-400/40 bg-emerald-400/10"
                          : "border-white/10 bg-slate-950/40 hover:border-white/20"
                      }`}
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="text-xs font-medium text-slate-200">
                          {incident.title}
                        </span>
                        <span className="shrink-0 text-[10px] text-slate-500">
                          {categoryLabels[incident.category]}
                        </span>
                      </span>
                      <span className="mt-1.5 flex flex-wrap gap-1">
                        <StatusBadge status={incident.status} />
                        <SeverityBadge severity={incident.severity} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
