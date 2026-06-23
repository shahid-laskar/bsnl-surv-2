// src/components/cameras/CameraCard.tsx
import { Link } from "react-router-dom";
import { Camera, MapPin, Video, Activity } from "lucide-react";
import { CameraStatusBadge } from "./CameraStatusBadge";
import { timeAgo } from "@/lib/utils";
import type { Camera as CameraType } from "@/types/api";

interface CameraCardProps {
  camera: CameraType;
}

export function CameraCard({ camera }: CameraCardProps) {
  return (
    <Link
      to={`/cameras/${camera.cam_id}`}
      className="group flex flex-col gap-3 rounded-lg border border-surface-border bg-surface-card p-4 transition-all hover:border-brand-700/50 hover:bg-surface-elevated"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-elevated">
            <Camera className="h-4 w-4 text-brand-400" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-gray-100 group-hover:text-white">
              {camera.cam_name}
            </p>
            <p className="font-mono text-[11px] text-gray-500">{camera.cam_id}</p>
          </div>
        </div>
        <CameraStatusBadge isOnline={camera.is_online} showLabel={false} />
      </div>

      {/* Details */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{camera.cam_loc}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Video className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{camera.strm_type}</span>
        </div>
        {camera.motion_active && (
          <div className="flex items-center gap-2 text-xs text-brand-400">
            <Activity className="h-3.5 w-3.5 shrink-0" />
            <span>Motion detection active</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-surface-border pt-2">
        <p className="text-[11px] text-gray-600">
          {camera.is_online
            ? "Streaming live"
            : camera.last_seen
              ? `Last seen ${timeAgo(camera.last_seen)}`
              : "Never connected"}
        </p>
      </div>
    </Link>
  );
}
