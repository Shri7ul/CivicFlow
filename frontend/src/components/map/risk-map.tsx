"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

import { useAuth } from "@/components/auth/auth-provider";
import {
  getRiskCell,
  getRiskCellsGeoJSON,
  getRiskConfig,
  getRiskDataQuality,
  getRiskSummary,
} from "@/lib/api/risk";
import {
  formatFactorValue,
  formatRiskConfidence,
  formatRiskDistance,
  formatRiskScore,
  riskCategoryColors,
  riskCategoryLabels,
  riskCategoryOrder,
  riskWindowLabels,
  trendTone,
  factorTone,
} from "@/lib/risk";
import { DEFAULT_MAP_VIEW, OSM_STYLE } from "@/lib/map";
import type {
  RiskCellDetail,
  RiskCellBrief,
  RiskConfig,
  RiskGeoJSON,
  RiskSummary,
  RiskTrend,
} from "@/types/risk";

type RiskWindow = "current" | "24h" | "7d" | "30d";
type Viewport = {
  minLatitude: number;
  minLongitude: number;
  maxLatitude: number;
  maxLongitude: number;
};

const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};
const selectClass =
  "rounded-lg border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-emerald-400/50";

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
  return error instanceof Error ? error.message : "Unable to load risk cells.";
}

function addRiskLayers(map: MapLibreMap) {
  map.addSource("risk-cells", { type: "geojson", data: EMPTY_COLLECTION });
  map.addSource("selected-risk-cell", {
    type: "geojson",
    data: EMPTY_COLLECTION,
  });
  map.addLayer({
    id: "risk-cells-fill",
    type: "fill",
    source: "risk-cells",
    paint: {
      "fill-color": [
        "match",
        ["get", "risk_category"],
        "CRITICAL",
        riskCategoryColors.CRITICAL,
        "HIGH",
        riskCategoryColors.HIGH,
        "MODERATE",
        riskCategoryColors.MODERATE,
        "LOW",
        riskCategoryColors.LOW,
        riskCategoryColors.MINIMAL,
      ],
      "fill-opacity": [
        "interpolate",
        ["linear"],
        ["get", "risk_score"],
        0,
        0.18,
        100,
        0.62,
      ],
    },
  });
  map.addLayer({
    id: "risk-cells-line",
    type: "line",
    source: "risk-cells",
    paint: {
      "line-color": [
        "match",
        ["get", "risk_category"],
        "CRITICAL",
        riskCategoryColors.CRITICAL,
        "HIGH",
        riskCategoryColors.HIGH,
        "MODERATE",
        riskCategoryColors.MODERATE,
        "LOW",
        riskCategoryColors.LOW,
        riskCategoryColors.MINIMAL,
      ],
      "line-width": 1.2,
      "line-opacity": 0.85,
    },
  });
  map.addLayer({
    id: "risk-cells-labels",
    type: "symbol",
    source: "risk-cells",
    layout: {
      "text-field": ["to-string", ["get", "risk_score"]],
      "text-size": 10,
      "text-font": ["Open Sans Regular"],
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#f8fafc",
      "text-halo-color": "#020617",
      "text-halo-width": 1.2,
    },
  });
  map.addLayer({
    id: "selected-risk-cell-line",
    type: "line",
    source: "selected-risk-cell",
    paint: {
      "line-color": "#f8fafc",
      "line-width": 3,
      "line-dasharray": [2, 1],
    },
  });
}

function trendText(trend: RiskTrend): string {
  if (!trend.available) return "Insufficient history";
  const sign = trend.delta_score > 0 ? "+" : "";
  return `${trend.direction_label} ${sign}${trend.delta_score.toFixed(1)}`;
}

function RiskLegend() {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-4 backdrop-blur">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        Risk category
      </p>
      <ul className="mt-3 space-y-2">
        {riskCategoryOrder.map((category) => (
          <li key={category} className="flex items-center gap-2 text-xs text-slate-300">
            <span
              aria-hidden="true"
              className="size-2.5 rounded-sm"
              style={{ backgroundColor: riskCategoryColors[category] }}
            />
            {riskCategoryLabels[category]}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[10px] leading-4 text-slate-500">
        Cell fill opacity also reflects the numeric score. Labels provide a
        non-color cue.
      </p>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
      {detail ? <p className="mt-1 text-[11px] text-slate-500">{detail}</p> : null}
    </div>
  );
}

function CellDetail({
  detail,
  loading,
}: {
  detail: RiskCellDetail | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-3" aria-label="Loading selected risk cell">
        <div className="h-20 animate-pulse rounded-2xl bg-white/[0.04]" />
        <div className="h-40 animate-pulse rounded-2xl bg-white/[0.04]" />
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 p-5 text-sm text-slate-500">
        Select an H3 cell on the map or from the top-risk list to inspect its
        score, factor contributions, trend, and infrastructure exposure.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="size-2.5 rounded-sm"
            style={{ backgroundColor: riskCategoryColors[detail.risk_category] }}
            aria-hidden="true"
          />
          <span className="text-xs font-semibold text-white">
            {riskCategoryLabels[detail.risk_category]} risk
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
            {detail.h3_cell_id}
          </span>
        </div>
        <p className="mt-2 text-2xl font-semibold text-white">
          {formatRiskScore(detail.risk_score)}
        </p>
        <p className="text-[11px] text-slate-500">
          Incident activity {formatRiskScore(detail.incident_activity_score)} ·{" "}
          {formatRiskConfidence(detail.confidence)} confidence ({detail.confidence_label})
        </p>
      </div>

      <div className={`rounded-xl border px-3 py-2 text-xs ${trendTone(detail.trend)}`}>
        <span className="font-medium">{trendText(detail.trend)}</span>
        <span className="ml-2 text-[10px] opacity-80">
          {detail.trend.current_incident_count} current /{" "}
          {detail.trend.previous_incident_count} previous
        </span>
      </div>

      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          Factor contributions
        </h3>
        <ul className="mt-2 space-y-2">
          {detail.factors.map((factor) => (
            <li key={factor.key}>
              <div className="flex items-center justify-between gap-2 text-[11px]">
                <span className={factorTone(factor)}>{factor.label}</span>
                <span className="font-mono text-slate-500">
                  {formatFactorValue(factor)} · +{(factor.contribution * 100).toFixed(1)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-emerald-400/80"
                  style={{ width: `${Math.round((factor.normalized ?? 0) * 100)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[10px] leading-4 text-slate-500">
          {detail.factors.map((factor) => factor.explanation).join(" ")}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <p className="text-slate-500">Incidents</p>
          <p className="mt-1 font-semibold text-white">
            {detail.incident_count} total / {detail.active_count} active
          </p>
          <p className="mt-0.5 text-slate-500">
            {detail.removed_duplicates} duplicate-adjusted
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <p className="text-slate-500">Nearby assets</p>
          <p className="mt-1 font-semibold text-white">
            {detail.infrastructure.nearby_asset_count}
          </p>
          <p className="mt-0.5 text-slate-500">
            {detail.infrastructure.dependency_count} dependency links
          </p>
        </div>
      </div>

      {detail.infrastructure.assets.length > 0 ? (
        <div>
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Inferred infrastructure exposure
          </h3>
          <ul className="mt-2 space-y-2">
            {detail.infrastructure.assets.map((asset) => (
              <li key={asset.id} className="text-[11px] text-slate-300">
                <span className="font-medium text-slate-200">{asset.name}</span>{" "}
                · {asset.asset_type} · {formatRiskDistance(asset.distance_m)} ·{" "}
                {asset.dependency_count} links
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] leading-4 text-slate-500">
            {detail.infrastructure.explanation}
          </p>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-white/10 p-3 text-[11px] text-slate-500">
          {detail.infrastructure.explanation}
        </p>
      )}

      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          Authorized incident briefs
        </h3>
        {detail.incidents.length === 0 ? (
          <p className="mt-2 text-[11px] leading-4 text-slate-500">
            No incident details are visible to you in this cell. Aggregate
            privacy rules still apply.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {detail.incidents.slice(0, 8).map((incident) => (
              <li key={incident.id} className="text-[11px]">
                <Link
                  href={`/incidents/${incident.id}`}
                  className="font-medium text-slate-200 underline-offset-2 hover:underline"
                >
                  {incident.title}
                </Link>
                <span className="ml-2 text-slate-500">
                  {incident.severity} · {incident.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-500">
        <div>
          <p className="font-semibold uppercase tracking-[0.12em]">Severity mix</p>
          <p className="mt-1">
            {Object.entries(detail.severity_distribution)
              .map(([key, value]) => `${key} ${value}`)
              .join(" · ") || "No adjusted incidents"}
          </p>
        </div>
        <div>
          <p className="font-semibold uppercase tracking-[0.12em]">Category mix</p>
          <p className="mt-1">
            {Object.entries(detail.category_distribution)
              .map(([key, value]) => `${key} ${value}`)
              .join(" · ") || "No adjusted incidents"}
          </p>
        </div>
      </div>

      <details className="rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2">
        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
          Model limitations
        </summary>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[10px] leading-4 text-slate-500">
          {detail.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export function RiskMapView() {
  const { apiRequest } = useAuth();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const requestRef = useRef(0);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [windowLabel, setWindowLabel] = useState<RiskWindow>("7d");
  const [resolution, setResolution] = useState(8);
  const [data, setData] = useState<RiskGeoJSON | null>(null);
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [quality, setQuality] = useState<
    Awaited<ReturnType<typeof getRiskDataQuality>>
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RiskCellDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      resolution,
      window: windowLabel,
      limit: config?.max_cells ?? 500,
      minLatitude: viewport?.minLatitude,
      minLongitude: viewport?.minLongitude,
      maxLatitude: viewport?.maxLatitude,
      maxLongitude: viewport?.maxLongitude,
    }),
    [config?.max_cells, resolution, viewport, windowLabel],
  );

  useEffect(() => {
    void getRiskConfig(apiRequest)
      .then((next) => {
        setConfig(next);
        setResolution(next.resolutions.default);
      })
      .catch(() => {
        // The map can still operate with its local legend defaults.
      });
  }, [apiRequest]);

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
          minZoom: 8,
          maxZoom: 19,
          attributionControl: false,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(new maplibre.AttributionControl({ compact: true }), "bottom-right");
        map.on("load", () => {
          if (disposed) return;
          addRiskLayers(map as MapLibreMap);
          (map as MapLibreMap).resize();
          (map as MapLibreMap).on("click", "risk-cells-fill", (event) => {
            const feature = event.features?.[0];
            const cellId = feature?.properties?.h3_cell_id;
            if (typeof cellId === "string") {
              setSelectedId(cellId);
            }
          });
          (map as MapLibreMap).on("mouseenter", "risk-cells-fill", () => {
            (map as MapLibreMap).getCanvas().style.cursor = "pointer";
          });
          (map as MapLibreMap).on("mouseleave", "risk-cells-fill", () => {
            (map as MapLibreMap).getCanvas().style.cursor = "";
          });
          setViewport(viewportFromMap(map as MapLibreMap));
          setMapReady(true);
        });
        map.on("error", (event) => {
          if (!disposed) setMapError(event.error?.message ?? "Map rendering failed.");
        });
        map.on("moveend", () => {
          if (!disposed && map) setViewport(viewportFromMap(map));
        });
        resizeObserver = new ResizeObserver(() => {
          if (!disposed) (map as MapLibreMap).resize();
        });
        resizeObserver.observe(containerRef.current);
      } catch (loadError) {
        if (!disposed) setMapError(errorMessage(loadError));
      }
    })();
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  const loadRisk = useCallback(
    async (signal?: AbortSignal) => {
      if (!viewport) return;
      const requestId = ++requestRef.current;
      setLoading(true);
      setError(null);
      try {
        const [nextData, nextSummary, nextQuality] = await Promise.all([
          getRiskCellsGeoJSON(apiRequest, filters, { signal }),
          getRiskSummary(apiRequest, filters, { signal }),
          getRiskDataQuality(apiRequest),
        ]);
        if (requestId !== requestRef.current) return;
        setData(nextData);
        setSummary(nextSummary);
        setQuality(nextQuality);
      } catch (loadError) {
        if (
          loadError instanceof Error &&
          "code" in loadError &&
          (loadError as { code?: string }).code === "request_cancelled"
        ) {
          return;
        }
        if (requestId !== requestRef.current) return;
        setError(errorMessage(loadError));
      } finally {
        if (requestId === requestRef.current) setLoading(false);
      }
    },
    [apiRequest, filters, viewport],
  );

  useEffect(() => {
    if (!mapReady || !viewport) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void loadRisk(controller.signal);
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [loadRisk, mapReady, viewport]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("risk-cells") as GeoJSONSource | undefined;
    if (!source || !data) return;
    source.setData(data as never);
  }, [data, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("selected-risk-cell") as GeoJSONSource | undefined;
    if (!source) return;
    const selected = data?.features.find((feature) => feature.id === selectedId);
    source.setData(
      selected
        ? {
            type: "FeatureCollection",
            features: [{ ...selected, properties: {} }],
          }
        : EMPTY_COLLECTION,
    );
  }, [data, mapReady, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setDetailLoading(true);
      setDetailError(null);
      void getRiskCell(apiRequest, selectedId, { resolution, window: windowLabel }, {
        signal: controller.signal,
      })
        .then((next) => setDetail(next))
        .catch((loadError) => {
          if (
            loadError instanceof Error &&
            "code" in loadError &&
            (loadError as { code?: string }).code === "request_cancelled"
          ) {
            return;
          }
          setDetailError(errorMessage(loadError));
        })
        .finally(() => setDetailLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [apiRequest, resolution, selectedId, windowLabel]);

  function selectCell(cell: RiskCellBrief) {
    // Clear the previous cell's detail immediately so it cannot remain visible
    // while the next cell is loading.
    setDetail(null);
    setDetailError(null);
    setSelectedId(cell.h3_cell_id);
    mapRef.current?.flyTo({
      center: [cell.center_longitude, cell.center_latitude],
      zoom: Math.max(11, mapRef.current.getZoom()),
      duration: 500,
    });
  }

  const categoryCounts = summary?.category_distribution ?? {};
  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Phase 5 · Urban risk engine
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            H3 risk map
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Observed incident activity is aggregated into H3 cells and combined
            with inferred infrastructure exposure. Select a cell to see its
            factors, trend, confidence, and limitations. Suggestions and scores
            are decision support, not confirmed impact.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            Window
            <select
              aria-label="Risk time window"
              value={windowLabel}
              onChange={(event) => setWindowLabel(event.target.value as RiskWindow)}
              className={`${selectClass} ml-2`}
            >
              {Object.entries(riskWindowLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            H3 resolution
            <select
              aria-label="H3 resolution"
              value={resolution}
              onChange={(event) => setResolution(Number(event.target.value))}
              className={`${selectClass} ml-2`}
            >
              {[7, 8, 9, 10]
                .filter(
                  (value) =>
                    (!config || value >= config.resolutions.min) &&
                    (!config || value <= config.resolutions.max),
                )
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
            </select>
          </label>
        </div>
      </div>

      {quality.some((item) => item.status !== "HEALTHY") ? (
        <div className="mt-5 rounded-xl border border-amber-300/25 bg-amber-300/10 p-3 text-xs text-amber-100">
          <p className="font-semibold">Data quality is not fully healthy.</p>
          <ul className="mt-1 space-y-1">
            {quality
              .filter((item) => item.status !== "HEALTHY")
              .map((item) => (
                <li key={item.source_id}>
                  {item.name}: {item.status}
                  {item.freshness_minutes === null
                    ? ""
                    : ` · ${item.freshness_minutes} min old`}
                  {item.issues.length > 0 ? ` · ${item.issues.join(" ")}` : ""}
                </li>
              ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <SummaryCard label="Risk cells" value={String(summary?.total_cells ?? "—")} />
        <SummaryCard
          label="Incidents"
          value={String(summary?.current_incident_count ?? "—")}
          detail={`${summary?.adjusted_incident_count ?? 0} adjusted`}
        />
        <SummaryCard
          label="High / critical"
          value={String(summary?.high_critical_cells ?? "—")}
          detail={`${summary?.increasing_cells ?? 0} increasing`}
        />
        <SummaryCard
          label="Mean score"
          value={summary ? formatRiskScore(summary.mean_risk_score) : "—"}
        />
        <SummaryCard
          label="Exposure cells"
          value={String(summary?.exposure_cells ?? "—")}
          detail={`${summary?.exposure_asset_count ?? 0} assets`}
        />
        <SummaryCard
          label="Confidence"
          value={summary ? formatRiskConfidence(summary.mean_confidence) : "—"}
          detail={`${summary?.insufficient_trend_cells ?? 0} low-history trends`}
        />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.55fr)]">
        <section className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03]">
          <div className="relative h-[560px] min-h-[420px]">
            <div ref={containerRef} className="h-[560px] w-full" aria-label="H3 risk map" />
            <div className="pointer-events-none absolute left-4 top-4">
              <div className="pointer-events-auto">
                <RiskLegend />
              </div>
            </div>
            {loading ? (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/40">
                <span className="rounded-full border border-white/10 bg-slate-950/90 px-4 py-2 text-xs text-slate-300">
                  Calculating risk cells…
                </span>
              </div>
            ) : null}
            {mapError ? (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 p-6">
                <div className="max-w-sm rounded-2xl border border-rose-300/20 bg-rose-300/5 p-5 text-sm text-rose-100">
                  <p>{mapError}</p>
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="mt-3 rounded-lg border border-white/15 px-3 py-1.5 text-xs"
                  >
                    Retry map
                  </button>
                </div>
              </div>
            ) : null}
            {!mapError && data && data.features.length === 0 && !loading ? (
              <div className="pointer-events-none absolute inset-x-6 bottom-6 rounded-2xl border border-white/10 bg-slate-950/90 p-4 text-xs text-slate-300">
                No risk cells are visible in this viewport and window. Pan or
                zoom out, choose a longer window, or note that Citizen views
                suppress cells below the privacy minimum.
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-4 py-3 text-[10px] text-slate-500">
            <span>
              {data?.model_version ?? "risk-v1"} · {data?.resolution ?? resolution} ·
              window {data?.window_hours ?? "—"}h
            </span>
            <span>
              Observed incident activity + inferred exposure · not confirmed impact
            </span>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">Highest risk cells</h2>
              <span className="text-[10px] text-slate-500">click to select</span>
            </div>
            {summary && summary.top_cells.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {summary.top_cells.map((cell) => (
                  <li key={cell.h3_cell_id}>
                    <button
                      type="button"
                      onClick={() => selectCell(cell)}
                      className={`w-full rounded-xl border px-3 py-2 text-left transition hover:border-white/25 ${
                        selectedId === cell.h3_cell_id
                          ? "border-emerald-300/40 bg-emerald-300/10"
                          : "border-white/10 bg-slate-950/40"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-200">
                          {cell.h3_cell_id}
                        </span>
                        <span className="text-xs font-semibold text-white">
                          {cell.risk_score.toFixed(1)}
                        </span>
                      </div>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {riskCategoryLabels[cell.risk_category]} ·{" "}
                        {cell.incident_count} incidents · {cell.trend_direction}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-xs text-slate-500">
                No top cells are available for this viewport.
              </p>
            )}
          </section>

          <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="text-sm font-semibold text-white">Selected risk cell</h2>
            {detailError ? (
              <p role="alert" className="mt-3 text-xs text-rose-200">
                {detailError}
              </p>
            ) : null}
            <div className="mt-3">
              <CellDetail detail={detail} loading={detailLoading} />
            </div>
          </section>

          {summary ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
              <h2 className="text-sm font-semibold text-white">Risk distribution</h2>
              <ul className="mt-3 space-y-2">
                {riskCategoryOrder.map((category) => (
                  <li key={category} className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex items-center gap-2 text-slate-300">
                      <span
                        aria-hidden="true"
                        className="size-2 rounded-sm"
                        style={{ backgroundColor: riskCategoryColors[category] }}
                      />
                      {riskCategoryLabels[category]}
                    </span>
                    <span className="font-mono text-slate-400">
                      {categoryCounts[category] ?? 0}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[10px] leading-4 text-slate-500">
                Dataset: {summary.dataset.active_asset_count} active assets,{" "}
                {summary.dataset.authoritative_asset_count} authoritative. History
                coverage {formatRiskConfidence(summary.history_coverage)}.
              </p>
            </section>
          ) : null}
        </aside>
      </div>

      {error ? (
        <div role="alert" className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-300/5 p-4 text-sm text-rose-100">
          {error}
          <button
            type="button"
            onClick={() => void loadRisk()}
            className="ml-3 rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white"
          >
            Retry
          </button>
        </div>
      ) : null}

      {config ? (
        <details className="mt-6 rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-3">
          <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Risk model and limitations
          </summary>
          <div className="mt-3 grid gap-4 text-[11px] leading-5 text-slate-400 sm:grid-cols-2">
            <div>
              <p className="font-semibold text-slate-300">
                {config.model_version} · config {config.config_hash.slice(0, 12)}
              </p>
              <p className="mt-1">
                Factor weights:{" "}
                {Object.entries(config.factor_weights)
                  .map(([key, value]) => `${key} ${(value * 100).toFixed(0)}%`)
                  .join(" · ")}
              </p>
              <p className="mt-1">
                H3 resolutions {config.resolutions.min}–{config.resolutions.max};
                default {config.resolutions.default}. Privacy minimum{" "}
                {config.privacy_min_incidents} incidents for Citizen views.
              </p>
            </div>
            <ul className="list-disc space-y-1 pl-4">
              {config.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
              {data?.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </details>
      ) : null}
    </main>
  );
}
