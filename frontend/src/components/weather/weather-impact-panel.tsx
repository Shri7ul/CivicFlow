"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
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
