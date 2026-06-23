// src/components/alerts/AlertList.tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { alertApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { Camera, CheckCircle, AlertTriangle } from "lucide-react";
import type { CameraAlert } from "@/types/api";
import { cn } from "@/lib/utils";
import { useAlertStore } from "@/stores/alertStore";

interface AlertListProps {
  alerts: CameraAlert[];
}

export function AlertList({ alerts }: AlertListProps) {
  const queryClient = useQueryClient();
  const { acknowledgeAlert } = useAlertStore();

  const acknowledgeMutation = useMutation({
    mutationFn: (id: number) => alertApi.acknowledge(id).then((r) => r.data),
    onSuccess: (_, id) => {
      acknowledgeAlert(id);
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <CheckCircle className="h-10 w-10 text-status-online mb-3" />
        <p className="text-sm font-medium text-gray-300">All clear</p>
        <p className="text-xs text-gray-500 mt-1">No alerts to show</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-surface-border">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={cn(
            "flex items-start gap-4 px-4 py-3 transition-colors",
            alert.acknowledged ? "opacity-50" : "hover:bg-surface-elevated",
          )}
        >
          {/* Icon */}
          <div
            className={cn(
              "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
              alert.status === "down"
                ? "bg-severity-critical/10"
                : "bg-status-online/10",
            )}
          >
            {alert.status === "down" ? (
              <AlertTriangle className="h-4 w-4 text-severity-critical" />
            ) : (
              <CheckCircle className="h-4 w-4 text-status-online" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Camera className="h-3.5 w-3.5 text-gray-500 shrink-0" />
              <span className="text-sm font-medium text-gray-200 truncate">
                {alert.cam_name}
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                  alert.status === "down"
                    ? "bg-severity-critical/10 text-severity-critical"
                    : "bg-status-online/10 text-status-online",
                )}
              >
                {alert.status === "down" ? "OFFLINE" : "ONLINE"}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-gray-500 truncate">{alert.cam_loc}</p>
            <p className="mt-1 text-[11px] text-gray-600">
              {formatDateTime(alert.timestamp)}
              {alert.duration && (
                <span className="ml-2 text-gray-600">· Duration: {alert.duration}</span>
              )}
            </p>
          </div>

          {/* Acknowledge button */}
          {!alert.acknowledged && alert.status === "down" && (
            <button
              onClick={() => acknowledgeMutation.mutate(alert.id)}
              disabled={acknowledgeMutation.isPending}
              className="shrink-0 rounded-md border border-surface-border px-2.5 py-1 text-xs font-medium text-gray-400 hover:border-brand-700/50 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              {acknowledgeMutation.isPending ? "…" : "Acknowledge"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
