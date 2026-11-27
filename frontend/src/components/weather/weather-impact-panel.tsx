"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { ApiError } from "@/lib/api/client";
import {
  WeatherAssessmentCard,
  type WeatherVariant,
} from "@/components/weather/weather-ui";
import {
  getWeatherAssessment,
  refreshWeatherAssessment,
} from "@/lib/api/weather";
import type { WeatherAssessment } from "@/types/weather";

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "Your role cannot view this weather assessment. The incident is unaffected.";
    }
    if (error.status === 404) {
      return "No weather assessment has been generated yet. Staff can request one; the incident is unaffected.";
    }
    if (
      error.code === "network_error" ||
      error.code === "request_timeout"
    ) {
      return "Weather context is temporarily unavailable. Your report and its status are unaffected; use Retry to reload only this panel.";
    }
    return error.message;
  }
  return error instanceof Error
    ? error.message
    : "Unable to load weather context.";
}

export function WeatherImpactPanel({ incidentId }: { incidentId: string }) {
  const { profile, apiRequest } = useAuth();
  const [assessment, setAssessment] = useState<WeatherAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const variant: WeatherVariant =
    profile?.role === "ADMIN"
      ? "admin"
      : profile?.role === "WORKER"
        ? "worker"
        : "citizen";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAssessment(await getWeatherAssessment(apiRequest, incidentId));
    } catch (cause) {
      setError(message(cause));
    } finally {
      setLoading(false);
    }
  }, [apiRequest, incidentId]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      if (active) void load();
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      setAssessment(await refreshWeatherAssessment(apiRequest, incidentId));
    } catch (cause) {
      setError(message(cause));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <WeatherAssessmentCard
      assessment={assessment}
      variant={variant}
      loading={loading}
      error={error}
      onRetry={() => void load()}
      onRefresh={() => void refresh()}
      refreshing={refreshing}
    />
  );
}
