// src/stores/alertStore.ts
// Global alert state managed by Zustand.
// Populated by the WebSocket hook and read by TopBar + AlertList.

import { create } from "zustand";
import type { CameraAlert } from "@/types/api";

interface AlertState {
  // Unacknowledged alert count (shown in TopBar badge)
  unreadCount: number;
  // Recent alerts (last 50)
  recentAlerts: CameraAlert[];
  // Whether the WebSocket is connected
  isConnected: boolean;

  // Actions
  addAlert: (alert: CameraAlert) => void;
  acknowledgeAlert: (id: number) => void;
  setConnected: (connected: boolean) => void;
  setInitialAlerts: (alerts: CameraAlert[]) => void;
  clearAll: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  unreadCount: 0,
  recentAlerts: [],
  isConnected: false,

  addAlert: (alert) =>
    set((state) => ({
      recentAlerts: [alert, ...state.recentAlerts].slice(0, 50),
      unreadCount: alert.status === "down" ? state.unreadCount + 1 : state.unreadCount,
    })),

  acknowledgeAlert: (id) =>
    set((state) => ({
      recentAlerts: state.recentAlerts.map((a) =>
        a.id === id ? { ...a, acknowledged: true } : a,
      ),
      unreadCount: Math.max(0, state.unreadCount - 1),
    })),

  setConnected: (connected) => set({ isConnected: connected }),

  setInitialAlerts: (alerts) =>
    set({
      recentAlerts: alerts,
      unreadCount: alerts.filter((a) => a.status === "down" && !a.acknowledged).length,
    }),

  clearAll: () => set({ unreadCount: 0, recentAlerts: [], isConnected: false }),
}));
