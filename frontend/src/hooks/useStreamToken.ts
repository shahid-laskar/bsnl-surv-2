// src/hooks/useStreamToken.ts
// Fetches a stream token for a camera and refreshes it every 13 minutes
// (tokens expire at 15 minutes — this gives a 2-minute safety window).

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { cameraApi } from "@/lib/api";
import type { StreamToken } from "@/types/api";

const REFRESH_INTERVAL_MS = 13 * 60 * 1000; // 13 minutes

interface UseStreamTokenResult {
  token: string | null;
  streamUrl: string | null;
  isLoading: boolean;
  error: string | null;
}

export function useStreamToken(camId: string | null): UseStreamTokenResult {
  const [tokenData, setTokenData] = useState<StreamToken | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchToken = useCallback(async () => {
    if (!camId) return;
    try {
      const { data } = await cameraApi.getStreamToken(camId);
      setTokenData(data);
      setError(null);
    } catch {
      setError("Failed to get stream token");
    }
  }, [camId]);

  useEffect(() => {
    if (!camId) return;

    setIsLoading(true);
    void fetchToken().finally(() => setIsLoading(false));

    // Auto-refresh before expiry
    intervalRef.current = setInterval(() => {
      void fetchToken();
    }, REFRESH_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [camId, fetchToken]);

  return {
    token: tokenData?.token ?? null,
    streamUrl: tokenData?.stream_url ?? null,
    isLoading,
    error,
  };
}
