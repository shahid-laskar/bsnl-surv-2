// src/pages/MotionPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motionApi, cameraApi } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/utils";
import { Activity, Loader2, Filter } from "lucide-react";

export function MotionPage() {
  const [camId, setCamId] = useState("");
  const [dateStr, setDateStr] = useState(new Date().toISOString().slice(0, 10));
  const [activeOnly, setActiveOnly] = useState(false);
  const [page, setPage] = useState(1);

  const { data: cameras } = useQuery({
    queryKey: ["cameras", "filter-list"],
    queryFn: () =>
      cameraApi.listAll({ is_active: true, page_size: 100 }).then((r) => r.data.items),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["motion-events", camId, dateStr, activeOnly, page],
    queryFn: () => {
      if (!camId) return Promise.resolve({ items: [], total: 0, pages: 1, page: 1, page_size: 50 });
      const startDate = new Date(dateStr);
      const endDate = new Date(dateStr);
      endDate.setDate(endDate.getDate() + 1);
      return motionApi
        .list(camId, {
          start: startDate.toISOString(),
          end: endDate.toISOString(),
          is_active: activeOnly || undefined,
          page,
          page_size: 50,
        })
        .then((r) => r.data);
    },
    enabled: !!camId,
  });

  const events = data?.items ?? [];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Motion Events</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {data?.total ?? 0} events recorded
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-surface-border bg-surface-card p-4">
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-1 w-full">
          <Filter className="h-3.5 w-3.5" />
          Filter events
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-gray-500">Camera</label>
          <select
            value={camId}
            onChange={(e) => { setCamId(e.target.value); setPage(1); }}
            className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none"
          >
            <option value="">All cameras</option>
            {(cameras ?? []).map((c) => (
              <option key={c.cam_id} value={c.cam_id}>
                {c.cam_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-gray-500">Date</label>
          <input
            type="date"
            value={dateStr}
            onChange={(e) => { setDateStr(e.target.value); setPage(1); }}
            className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none"
          />
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => { setActiveOnly(e.target.checked); setPage(1); }}
            className="rounded border-surface-border bg-surface accent-brand-500"
          />
          Active only
        </label>
      </div>

      {/* Events list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Activity className="h-10 w-10 text-gray-600 mb-3" />
          <p className="text-sm font-medium text-gray-300">No motion events</p>
          <p className="text-xs text-gray-500 mt-1">No events in the selected range</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border bg-surface-elevated">
                <th className="px-4 py-3 text-left font-medium text-gray-400">Camera</th>
                <th className="px-4 py-3 text-left font-medium text-gray-400">Started</th>
                <th className="px-4 py-3 text-left font-medium text-gray-400">Ended</th>
                <th className="px-4 py-3 text-left font-medium text-gray-400">Duration</th>
                <th className="px-4 py-3 text-left font-medium text-gray-400">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-surface-elevated transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-200">{cameras?.find(c => c.cam_id === camId)?.cam_name ?? camId}</p>
                    <p className="font-mono text-[11px] text-gray-500">{camId}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {formatDateTime(event.motion_start)}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {event.motion_end ? formatDateTime(event.motion_end) : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-400">
                    {event.duration_seconds ? formatDuration(event.duration_seconds) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {event.is_active ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-status-online/10 px-2 py-0.5 text-xs font-medium text-status-online">
                        <span className="h-1.5 w-1.5 animate-ping rounded-full bg-status-online" />
                        Active
                      </span>
                    ) : (
                      <span className="rounded-full bg-gray-700/30 px-2 py-0.5 text-xs text-gray-500">
                        Ended
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {(data?.pages ?? 1) > 1 && (
        <div className="flex items-center justify-center gap-2">
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
    </div>
  );
}
