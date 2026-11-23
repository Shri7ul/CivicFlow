"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchBackendHealth } from "@/lib/api/health";
import type { BackendHealth, BackendHealthState } from "@/types/health";

const initialState: BackendHealthState = {
  status: "loading",
  data: null,
  error: null,
  checkedAt: null,
};

function healthyState(data: BackendHealth): BackendHealthState {
  return {
    status: "healthy",
    data,
    error: null,
    checkedAt: new Date().toISOString(),
  };
}

function errorState(error: unknown): BackendHealthState {
  return {
    status: "error",
    data: null,
    error:
      error instanceof Error
        ? error.message
        : "Unable to reach the CivicFlow API.",
    checkedAt: new Date().toISOString(),
  };
}

export function useBackendHealth() {
  const [state, setState] = useState<BackendHealthState>(initialState);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;

    setState((previous) => ({
      ...previous,
      status: "loading",
      error: null,
    }));

    try {
      const data = await fetchBackendHealth();
      if (requestId.current === currentRequest) {
        setState(healthyState(data));
      }
    } catch (error) {
      if (requestId.current === currentRequest) {
        setState(errorState(error));
      }
    }
  }, []);

  useEffect(() => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;

    fetchBackendHealth()
      .then((data) => {
        if (requestId.current === currentRequest) {
          setState(healthyState(data));
        }
      })
      .catch((error: unknown) => {
        if (requestId.current === currentRequest) {
          setState(errorState(error));
        }
      });

    return () => {
      requestId.current += 1;
    };
  }, []);

  return { ...state, refresh };
}
