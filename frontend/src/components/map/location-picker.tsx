"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap, Marker } from "maplibre-gl";

import { reverseGeocode } from "@/lib/geocoding";
import {
  DEFAULT_MAP_VIEW,
  MAX_MAP_ZOOM,
  MIN_MAP_ZOOM,
  OSM_STYLE,
} from "@/lib/map";

type LocationPickerProps = {
  latitude: string;
  longitude: string;
  onChange: (latitude: string, longitude: string) => void;
};

function numeric(value: string, fallback: number): number {
  if (value.trim() === "") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function LocationPicker({
  latitude,
  longitude,
  onChange,
}: LocationPickerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const onChangeRef = useRef(onChange);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [address, setAddress] = useState<string | null>(null);
  const [resolvingAddress, setResolvingAddress] = useState(false);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let disposed = false;
    let map: MapLibreMap | null = null;

    void (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (disposed || !containerRef.current) {
          return;
        }
        const lat = numeric(latitude, DEFAULT_MAP_VIEW.latitude);
        const lon = numeric(longitude, DEFAULT_MAP_VIEW.longitude);
        map = new maplibre.Map({
          container: containerRef.current,
          style: OSM_STYLE,
          center: [lon, lat],
          zoom: 13,
          minZoom: MIN_MAP_ZOOM,
          maxZoom: MAX_MAP_ZOOM,
          attributionControl: false,
        });
        mapRef.current = map;
        const activeMap = map;
        map.addControl(
          new maplibre.NavigationControl({ showCompass: false }),
          "top-right",
        );
        map.addControl(
          new maplibre.AttributionControl({ compact: true }),
          "bottom-right",
        );
        // No marker is shown until a real location is chosen. Rendering a
        // marker at the map's default center would present a fabricated pin.
        const hasLocation = latitude.trim() !== "" && longitude.trim() !== "";
        markerRef.current = hasLocation
          ? new maplibre.Marker({ color: "#34d399" })
              .setLngLat([lon, lat])
              .addTo(map)
          : null;
        map.on("click", (event) => {
          const nextLat = event.lngLat.lat.toFixed(6);
          const nextLon = event.lngLat.lng.toFixed(6);
          if (markerRef.current) {
            markerRef.current.setLngLat([event.lngLat.lng, event.lngLat.lat]);
          } else {
            markerRef.current = new maplibre.Marker({ color: "#34d399" })
              .setLngLat([event.lngLat.lng, event.lngLat.lat])
              .addTo(activeMap);
          }
          onChangeRef.current(nextLat, nextLon);
        });
        map.on("load", () => {
          if (!disposed) setReady(true);
        });
      } catch (loadError) {
        if (!disposed) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load the location picker.",
          );
        }
      }
    })();

    return () => {
      disposed = true;
      mapRef.current = null;
      markerRef.current = null;
      map?.remove();
    };
    // Initial center is intentionally captured once; later prop changes move
    // the marker through the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || !markerRef.current) {
      return;
    }
    if (latitude.trim() === "" || longitude.trim() === "" || !markerRef.current) {
      return;
    }
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (
      Number.isFinite(lat) &&
      Number.isFinite(lon) &&
      lat >= -90 &&
      lat <= 90 &&
      lon >= -180 &&
      lon <= 180
    ) {
      markerRef.current.setLngLat([lon, lat]);
    }
  }, [latitude, longitude, ready]);

  useEffect(() => {
    if (latitude.trim() === "" || longitude.trim() === "") {
      const timer = setTimeout(() => {
        setAddress(null);
        setResolvingAddress(false);
      }, 0);
      return () => clearTimeout(timer);
    }
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < -90 ||
      lat > 90 ||
      lon < -180 ||
      lon > 180
    ) {
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setResolvingAddress(true);
      void reverseGeocode(lat, lon, controller.signal)
        .then((label) => {
          if (!controller.signal.aborted) setAddress(label);
        })
        .finally(() => {
          if (!controller.signal.aborted) setResolvingAddress(false);
        });
    }, 600);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [latitude, longitude]);

  const hasCoordinates = latitude.trim() !== "" && longitude.trim() !== "";

  return (
    <div className="mt-4">
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-950">
        <div
          ref={containerRef}
          className="h-[260px] w-full"
          aria-label="Click the map to choose the incident location"
          role="application"
        />
        {!ready && !error ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/70">
            <span className="text-xs text-slate-300">Loading map picker…</span>
          </div>
        ) : null}
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/95 p-4 text-center">
            <span className="text-xs text-rose-200">{error}</span>
          </div>
        ) : null}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        Click the map to place the pin, or enter coordinates manually. The area
        name is resolved from the coordinates using OpenStreetMap.
      </p>
      <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/50 p-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
          Selected location
        </p>
        {hasCoordinates ? (
          <>
            <p className="mt-1 text-sm text-slate-200">
              {address ?? "Address lookup unavailable"}
              {resolvingAddress ? (
                <span className="ml-2 text-xs text-slate-500">
                  Resolving address…
                </span>
              ) : null}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400">
              {Number(latitude).toFixed(6)}, {Number(longitude).toFixed(6)}
            </p>
          </>
        ) : (
          <p className="mt-1 text-sm text-slate-400">
            No pin placed yet — click the map or use your current location.
          </p>
        )}
      </div>
    </div>
  );
}
