"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { LocationPicker } from "@/components/map/location-picker";
import { createIncident } from "@/lib/api/incidents";
import {
  categories,
  categoryLabels,
  severities,
  severityLabels,
} from "@/lib/incidents";
import type { IncidentCategory, IncidentSeverity } from "@/types/incidents";

const inputClass =
  "mt-1.5 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3.5 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50";
const labelClass =
  "text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to report incident.";
}

export function ReportIncidentForm() {
  const { apiRequest } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<IncidentCategory>("DRAINAGE");
  const [severity, setSeverity] = useState<IncidentSeverity>("MEDIUM");
  const [latitude, setLatitude] = useState("23.8103");
  const [longitude, setLongitude] = useState("90.4125");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError("Geolocation is not available in this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude.toFixed(6));
        setLongitude(position.coords.longitude.toFixed(6));
        setLocating(false);
      },
      (positionError) => {
        setError(
          positionError.code === positionError.PERMISSION_DENIED
            ? "Location permission was denied. Enter coordinates manually or click the map."
            : positionError.code === positionError.TIMEOUT
              ? "Location lookup timed out. Try again or place the pin on the map."
              : "Your location is unavailable. Enter coordinates manually or click the map.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Latitude must be between -90 and 90.");
      return;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setError("Longitude must be between -180 and 180.");
      return;
    }
    setSubmitting(true);
    try {
      const incident = await createIncident(apiRequest, {
        title: title.trim(),
        description: description.trim(),
        category,
        severity,
        latitude: lat,
        longitude: lon,
        address: address.trim() || null,
      });
      router.push(`/incidents/${incident.id}`);
    } catch (submitError) {
      setError(message(submitError));
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-12 sm:px-8">
      <Link
        href="/incidents"
        className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 transition hover:text-slate-300"
      >
        ← Back to incidents
      </Link>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
        Report an incident
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-400">
        Pin the location and describe what you observed. Your report starts as
        Open and is visible to you and municipal staff.
      </p>

      <form
        onSubmit={onSubmit}
        className="mt-8 space-y-6 rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8"
      >
        <div>
          <label htmlFor="title" className={labelClass}>
            Title
          </label>
          <input
            id="title"
            required
            minLength={3}
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Blocked storm drain near the school"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="description" className={labelClass}>
            Description
          </label>
          <textarea
            id="description"
            required
            minLength={10}
            maxLength={10000}
            rows={5}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What is happening, who is affected, and how urgent is it?"
            className={inputClass}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="category" className={labelClass}>
              Category
            </label>
            <select
              id="category"
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as IncidentCategory)
              }
              className={inputClass}
            >
              {categories.map((value) => (
                <option key={value} value={value}>
                  {categoryLabels[value]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="severity" className={labelClass}>
              Severity
            </label>
            <select
              id="severity"
              value={severity}
              onChange={(event) =>
                setSeverity(event.target.value as IncidentSeverity)
              }
              className={inputClass}
            >
              {severities.map((value) => (
                <option key={value} value={value}>
                  {severityLabels[value]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <fieldset className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <legend className="px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Location
          </legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="latitude" className={labelClass}>
                Latitude
              </label>
              <input
                id="latitude"
                type="number"
                step="0.000001"
                min="-90"
                max="90"
                required
                value={latitude}
                onChange={(event) => setLatitude(event.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="longitude" className={labelClass}>
                Longitude
              </label>
              <input
                id="longitude"
                type="number"
                step="0.000001"
                min="-180"
                max="180"
                required
                value={longitude}
                onChange={(event) => setLongitude(event.target.value)}
                className={inputClass}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={useCurrentLocation}
            disabled={locating}
            className="mt-4 rounded-lg border border-white/15 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-white/25 disabled:opacity-50"
          >
            {locating ? "Locating…" : "Use my current location"}
          </button>
          <LocationPicker
            latitude={latitude}
            longitude={longitude}
            onChange={(nextLatitude, nextLongitude) => {
              setLatitude(nextLatitude);
              setLongitude(nextLongitude);
            }}
          />
          <div className="mt-4">
            <label htmlFor="address" className={labelClass}>
              Address or landmark (optional)
            </label>
            <input
              id="address"
              maxLength={500}
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              placeholder="Road 12, Dhanmondi"
              className={inputClass}
            />
          </div>
        </fieldset>

        {error ? (
          <p
            role="alert"
            className="rounded-xl border border-rose-300/20 bg-rose-300/5 px-4 py-3 text-sm text-rose-100"
          >
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-xl bg-emerald-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-60"
          >
            {submitting ? "Submitting…" : "Submit report"}
          </button>
          <Link
            href="/incidents"
            className="rounded-xl border border-white/15 px-5 py-2.5 text-sm font-medium text-white"
          >
            Cancel
          </Link>
        </div>
      </form>
    </main>
  );
}
