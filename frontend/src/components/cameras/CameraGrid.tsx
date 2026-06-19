// src/components/cameras/CameraGrid.tsx
"use client";

import { useState } from "react";
import { CameraPlayer } from "./CameraPlayer";
import type { Camera } from "@/types/api";
import { Grid2x2, Grid3x3, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";

type GridSize = 2 | 3 | 4;

interface CameraGridProps {
  cameras: Camera[];
}

const GRID_CLASSES: Record<GridSize, string> = {
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
};

export function CameraGrid({ cameras }: CameraGridProps) {
  const [gridSize, setGridSize] = useState<GridSize>(2);
  const [selectedCamId, setSelectedCamId] = useState<string | null>(null);

  const visibleCameras = cameras.slice(0, gridSize * gridSize);

  const selectedCamera = selectedCamId
    ? cameras.find((c) => c.cam_id === selectedCamId)
    : null;

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Grid size controls */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">
          Showing {visibleCameras.length} of {cameras.length} cameras
        </p>
        <div className="flex items-center gap-1 rounded-lg border border-surface-border bg-surface-elevated p-1">
          {([2, 3, 4] as GridSize[]).map((size) => {
            const Icon = size === 2 ? Grid2x2 : size === 3 ? Grid3x3 : LayoutGrid;
            return (
              <button
                key={size}
                onClick={() => setGridSize(size)}
                className={cn(
                  "flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  gridSize === size
                    ? "bg-brand-700 text-white"
                    : "text-gray-400 hover:text-gray-200",
                )}
                title={`${size}×${size} grid`}
              >
                <Icon className="h-3.5 w-3.5" />
                {size}×{size}
              </button>
            );
          })}
        </div>
      </div>

      {/* Camera grid */}
      <div className={cn("grid gap-2 flex-1", GRID_CLASSES[gridSize])}>
        {visibleCameras.map((camera) => (
          <div
            key={camera.cam_id}
            className="cursor-pointer"
            onClick={() => setSelectedCamId(camera.cam_id)}
          >
            <CameraPlayer
              camId={camera.cam_id}
              camName={camera.cam_name}
              isOnline={camera.is_online}
            />
          </div>
        ))}

        {/* Empty cells to fill grid */}
        {Array.from({ length: gridSize * gridSize - visibleCameras.length }).map(
          (_, i) => (
            <div
              key={`empty-${i}`}
              className="aspect-video w-full rounded-lg border border-dashed border-surface-border bg-surface flex items-center justify-center"
            >
              <span className="text-xs text-gray-600">No camera</span>
            </div>
          ),
        )}
      </div>

      {/* Fullscreen modal */}
      {selectedCamera && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setSelectedCamId(null)}
        >
          <div
            className="w-full max-w-5xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-200">
                {selectedCamera.cam_name} — {selectedCamera.cam_loc}
              </span>
              <button
                onClick={() => setSelectedCamId(null)}
                className="text-xs text-gray-400 hover:text-gray-200"
              >
                Close ✕
              </button>
            </div>
            <CameraPlayer
              camId={selectedCamera.cam_id}
              camName={selectedCamera.cam_name}
              isOnline={selectedCamera.is_online}
              fullscreen
            />
          </div>
        </div>
      )}
    </div>
  );
}
