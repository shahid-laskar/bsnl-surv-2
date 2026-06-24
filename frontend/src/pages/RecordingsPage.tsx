// src/pages/RecordingsPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { recordingApi, cameraApi } from "@/lib/api";
import { RecordingTable } from "@/components/recordings/RecordingTable";
import { RecordingPlayer } from "@/components/recordings/RecordingPlayer";
import { todayRange } from "@/lib/utils";
import type { TimelineSegment, TimelineResponse } from "@/types/api";
import { Loader2, Filter } from "lucide-react";

export function RecordingsPage() {
  const { start: defaultStart, end: defaultEnd } = todayRange();

  const [camId, setCamId] = useState("");
  const [start, setStart] = useState(defaultStart.slice(0, 16));
  const [end, setEnd] = useState(defaultEnd.slice(0, 16));
  const [playingSegment, setPlayingSegment] = useState<TimelineSegment | null>(null);

  const { data: cameras } = useQuery({
    queryKey: ["cameras", "filter-list"],
    queryFn: () =>
      cameraApi.listAll({ is_active: true, page_size: 100 }).then((r) => r.data.items),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["recordings", camId, start, end],
    queryFn: () => {
      if (!camId) return Promise.resolve({ segments: [], segment_count: 0 } as unknown as TimelineResponse);
      return recordingApi
        .getTimeline(camId, new Date(start).toISOString(), new Date(end).toISOString())
        .then((r) => r.data);
    },
    enabled: !!start && !!end && !!camId,
  });

  const selectedCamName = cameras?.find(c => c.cam_id === camId)?.cam_name ?? camId;

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Recordings</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {data?.segment_count ?? 0} segments in selected range
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-surface-border bg-surface-card p-4">
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-1 w-full">
          <Filter className="h-3.5 w-3.5" />
          Filter recordings
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-gray-500">Camera</label>
          <select
            value={camId}
            onChange={(e) => { setCamId(e.target.value); }}
            className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          >
            <option value="" disabled>Select a camera</option>
            {(cameras ?? []).map((c) => (
              <option key={c.cam_id} value={c.cam_id}>
                {c.cam_name} ({c.cam_id})
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-gray-500">From</label>
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => { setStart(e.target.value); }}
            className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-gray-500">To</label>
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => { setEnd(e.target.value); }}
            className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          />
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
        </div>
      ) : (
        <>
          {camId ? (
            <RecordingTable
              segments={data?.segments ?? []}
              onSegmentClick={setPlayingSegment}
              camId={camId}
              camName={selectedCamName}
            />
          ) : (
            <div className="flex items-center justify-center py-20">
              <p className="text-sm text-gray-500">Please select a camera to view recordings.</p>
            </div>
          )}
        </>
      )}

      {/* Video player modal */}
      {playingSegment && (
        <RecordingPlayer
          segment={playingSegment}
          camName={selectedCamName}
          onClose={() => setPlayingSegment(null)}
        />
      )}
    </div>
  );
}
