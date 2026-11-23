"use client";

import { BackendStatusCard } from "@/components/status/backend-status-card";
import { useBackendHealth } from "@/hooks/use-backend-health";
import { getApiBaseUrl } from "@/lib/api/client";
import { HEALTH_ENDPOINT } from "@/lib/api/health";

export function BackendStatus() {
  const { status, data, error, checkedAt, refresh } = useBackendHealth();

  return (
    <BackendStatusCard
      state={{ status, data, error, checkedAt }}
      endpoint={`${getApiBaseUrl()}${HEALTH_ENDPOINT}`}
      onRefresh={() => {
        void refresh();
      }}
    />
  );
}
