// src/components/cameras/CameraStatusBadge.tsx
"use client";

import { cn } from "@/lib/utils";

interface CameraStatusBadgeProps {
  isOnline: boolean;
  className?: string;
  showLabel?: boolean;
  pulse?: boolean;
}

export function CameraStatusBadge({
  isOnline,
  className,
  showLabel = true,
  pulse = true,
}: CameraStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        isOnline
          ? "bg-status-online/10 text-status-online"
          : "bg-status-offline/10 text-status-offline",
        className,
      )}
    >
      <span className="relative flex h-2 w-2">
        {isOnline && pulse && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-online opacity-60" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            isOnline ? "bg-status-online" : "bg-status-offline",
          )}
        />
      </span>
      {showLabel && (isOnline ? "Online" : "Offline")}
    </span>
  );
}
