// src/pages/CameraDetailPage.tsx
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { cameraApi, recordingApi } from "@/lib/api";
import { CameraPlayer } from "@/components/cameras/CameraPlayer";
import { CameraStatusBadge } from "@/components/cameras/CameraStatusBadge";
import { RecordingTable } from "@/components/recordings/RecordingTable";
import { RecordingPlayer } from "@/components/recordings/RecordingPlayer";
import { useState } from "react";
import {
  MapPin,
  Video,
  Activity,
  ArrowLeft,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { todayRange } from "@/lib/utils";
import type { TimelineSegment } from "@/types/api";

export function CameraDetailPage() {
  const { id: camId } = useParams<{ id: string }>();
  const [playingSegment, setPlayingSegment] = useState<TimelineSegment | null>(null);

  const { start, end } = todayRange();

  const { data: camera, isLoading: cameraLoading } = useQuery({
    queryKey: ["cameras", camId],
    queryFn: () => cameraApi.get(camId!).then((r) => r.data),
    enabled: !!camId,
    refetchInterval: 30_000,
  });

  const { data: recordings, isLoading: recordingsLoading } = useQuery({
    queryKey: ["recordings", camId, start, end],
    queryFn: () =>
      recordingApi
        .getTimeline(camId!, new Date(start).toISOString(), new Date(end).toISOString())
        .then((r) => r.data),
    enabled: !!camera,
  });

  if (cameraLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
      </div>
    );
  }

  if (!camera) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <AlertTriangle className="h-10 w-10 text-severity-warning" />
        <p className="text-sm text-gray-400">Camera not found</p>
        <Link to="/cameras" className="text-xs text-brand-400 hover:underline">
          Back to cameras
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Back nav */}
      <Link
        to="/cameras"
        className="flex w-fit items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All cameras
      </Link>

      {/* Camera header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-100">{camera.cam_name}</h2>
            <CameraStatusBadge isOnline={!!camera.is_online} />
          </div>
          <p className="font-mono text-xs text-gray-500 mt-0.5">{camera.cam_id}</p>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs text-gray-500">
          <div className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5" />
            {camera.cam_loc}
          </div>
          <div className="flex items-center gap-1.5">
            <Video className="h-3.5 w-3.5" />
            Stream ID: {camera.strm_type_id ?? 'Unknown'} · {camera.cam_make}
          </div>
          {camera.motion_active && (
            <div className="flex items-center gap-1.5 text-brand-400">
              <Activity className="h-3.5 w-3.5" />
              Motion detection active
            </div>
          )}
        </div>
      </div>

      {/* Live player */}
      <div className="w-full max-w-3xl">
        <CameraPlayer
          camId={camera.cam_id}
          camName={camera.cam_name}
          isOnline={!!camera.is_online}
        />
      </div>

      {/* Today's recordings */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-200">
          Today&apos;s recordings
        </h3>
        {recordingsLoading ? (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading recordings…
          </div>
        ) : (
          <RecordingTable
            segments={recordings?.segments ?? []}
            camId={camera.cam_id}
            camName={camera.cam_name}
            onSegmentClick={setPlayingSegment}
          />
        )}
      </div>

      {/* Recording player modal */}
      {playingSegment && (
        <RecordingPlayer
          segment={playingSegment}
          camName={camera.cam_name}
          onClose={() => setPlayingSegment(null)}
        />
      )}
    </div>
  );
}
