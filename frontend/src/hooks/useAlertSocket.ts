// src/hooks/useAlertSocket.ts
// WebSocket connection to the FastAPI alert feed.
// Manages connection lifecycle with exponential-backoff reconnect.

import { useEffect, useRef } from "react";
import { useSession } from "@/contexts/AuthContext";
import { useAlertStore } from "@/stores/alertStore";
import type { CameraAlert } from "@/types/api";

const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";
const MAX_RECONNECT_DELAY_MS = 30_000;

export function useAlertSocket(): void {
  const { data: session } = useSession();
  const { addAlert, setConnected } = useAlertStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!session?.accessToken) return;

    function connect() {
      if (!isMountedRef.current) return;

      const url = `${WS_BASE}/api/v1/ws/alerts?token=${session!.accessToken}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        reconnectAttemptRef.current = 0;
        setConnected(true);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        if (!isMountedRef.current) return;
        try {
          const alert = JSON.parse(event.data) as CameraAlert;
          addAlert(alert);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setConnected(false);

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptRef.current),
          MAX_RECONNECT_DELAY_MS,
        );
        reconnectAttemptRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      setConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken]);
}
