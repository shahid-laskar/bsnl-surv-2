// src/pages/CamerasPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cameraApi } from "@/lib/api";
import { CameraCard } from "@/components/cameras/CameraCard";
import { RoleGuard } from "@/components/layout/RoleGuard";
import { Plus, Search, Loader2, Camera } from "lucide-react";
import { Link } from "react-router-dom";

export function CamerasPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["cameras", page],
    queryFn: () =>
      cameraApi.list({ is_active: true, page, page_size: 24 }).then((r) => r.data),
  });

  const cameras = data?.items ?? [];
  const filtered = cameras.filter(
    (c) =>
      c.cam_name.toLowerCase().includes(search.toLowerCase()) ||
      c.cam_id.toLowerCase().includes(search.toLowerCase()) ||
      c.cam_loc.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Cameras</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {data?.total ?? 0} cameras registered
          </p>
        </div>
        <RoleGuard roles={["sysadmin", "circle_admin"]}>
          <Link
            to="/cameras/add"
            className="flex items-center gap-2 rounded-lg bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add Camera
          </Link>
        </RoleGuard>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
        <input
          type="text"
          placeholder="Search by name, ID, or location…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-surface-border bg-surface-card py-2.5 pl-9 pr-4 text-sm text-gray-100 placeholder-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-colors"
        />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Camera className="h-12 w-12 text-gray-600 mb-3" />
          <p className="text-sm font-medium text-gray-300">
            {search ? "No cameras match your search" : "No cameras yet"}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((camera) => (
              <CameraCard key={camera.cam_id} camera={camera} />
            ))}
          </div>

          {/* Pagination */}
          {(data?.pages ?? 1) > 1 && (
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                className="rounded-md border border-surface-border px-3 py-1.5 text-xs text-gray-400 hover:bg-surface-elevated disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs text-gray-500">
                Page {page} of {data?.pages}
              </span>
              <button
                disabled={page === (data?.pages ?? 1)}
                onClick={() => setPage(page + 1)}
                className="rounded-md border border-surface-border px-3 py-1.5 text-xs text-gray-400 hover:bg-surface-elevated disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
