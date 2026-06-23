// src/app/(dashboard)/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { dashboardApi, cameraApi } from "@/lib/api";
import { CameraGrid } from "@/components/cameras/CameraGrid";
import { Camera, Wifi, Activity, Video, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ElementType;
  accent?: "brand" | "online" | "offline" | "warning";
}

function StatCard({ label, value, icon: Icon, accent = "brand" }: StatCardProps) {
  const accentClasses = {
    brand: "bg-brand-700/10 text-brand-400",
    online: "bg-status-online/10 text-status-online",
    offline: "bg-status-offline/10 text-status-offline",
    warning: "bg-status-degraded/10 text-status-degraded",
  };

  return (
    <div className="flex items-center gap-4 rounded-lg border border-surface-border bg-surface-card p-4">
      <div
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          accentClasses[accent],
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-100 tabular-nums">{value}</p>
        <p className="text-xs text-gray-500">{label}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => dashboardApi.getStats().then((r) => r.data),
    refetchInterval: 30_000, // Refresh every 30 seconds
  });

  const { data: camerasPage, isLoading: camerasLoading } = useQuery({
    queryKey: ["cameras", "dashboard"],
    queryFn: () =>
      cameraApi.list({ is_active: true, page_size: 16 }).then((r) => r.data),
    refetchInterval: 30_000,
  });

  const cameras = camerasPage?.items ?? [];
  const onlineCount = stats?.active_cameras.length ?? 0;
  const totalCount = stats?.all_added_streams ?? 0;
  const offlineCount = totalCount - onlineCount;

  return (
    <div className="flex h-full flex-col gap-5">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Total cameras"
          value={statsLoading ? "—" : totalCount}
          icon={Camera}
          accent="brand"
        />
        <StatCard
          label="Online now"
          value={statsLoading ? "—" : onlineCount}
          icon={Wifi}
          accent="online"
        />
        <StatCard
          label="Offline"
          value={statsLoading ? "—" : offlineCount}
          icon={Camera}
          accent={offlineCount > 0 ? "offline" : "brand"}
        />
        <StatCard
          label="Live viewers"
          value={statsLoading ? "—" : (stats?.live_cameras.length ?? 0)}
          icon={Video}
          accent="warning"
        />
      </div>

      {/* Camera grid */}
      <div className="flex-1 min-h-0">
        {camerasLoading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
          </div>
        ) : cameras.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <Camera className="h-12 w-12 text-gray-600" />
            <div>
              <p className="text-sm font-medium text-gray-300">No cameras configured</p>
              <p className="text-xs text-gray-500 mt-1">
                Add cameras from the Cameras section
              </p>
            </div>
          </div>
        ) : (
          <CameraGrid cameras={cameras} />
        )}
      </div>
    </div>
  );
}