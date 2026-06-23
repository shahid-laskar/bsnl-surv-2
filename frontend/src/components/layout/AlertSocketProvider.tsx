// src/components/layout/AlertSocketProvider.tsx
import { useAlertSocket } from "@/hooks/useAlertSocket";

// This component's only job is to mount the WebSocket hook
// at the layout level so alerts flow to all pages.
export function AlertSocketProvider({ children }: { children: React.ReactNode }) {
  useAlertSocket();
  return <>{children}</>;
}
