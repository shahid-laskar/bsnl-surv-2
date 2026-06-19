// src/components/cameras/CameraPlayer.tsx
// HLS.js player with automatic stream token refresh.
// Handles offline cameras gracefully.
"use client";

import { useEffect, useRef, useState } from "react";
import Hls, { type ErrorData, Events } from "hls.js";
import { useStreamToken } from "@/hooks/useStreamToken";
import { CameraStatusBadge } from "./CameraStatusBadge";
import { Camera, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface CameraPlayerProps {
  camId: string;
  camName: string;
  isOnline: boolean;
  className?: string;
  /** If true, player renders at full-screen proportions */
  fullscreen?: boolean;
}

type PlayerState = "loading" | "playing" | "error" | "offline";

export function CameraPlayer({
  camId,
  camName,
  isOnline,
  className,
  fullscreen = false,
}: CameraPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState>(
    isOnline ? "loading" : "offline",
  );

  const { streamUrl, isLoading: tokenLoading, error: tokenError } = useStreamToken(
    isOnline ? camId : null,
  );

  // Initialise or re-initialise HLS when stream URL changes
  useEffect(() => {
    if (!isOnline) {
      setPlayerState("offline");
      return;
    }

    if (!streamUrl || !videoRef.current) return;

    // Destroy previous instance
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 30,
      });

      hlsRef.current = hls;

      hls.loadSource(streamUrl);
      hls.attachMedia(videoRef.current);

      hls.on(Events.MANIFEST_PARSED, () => {
        setPlayerState("playing");
        void videoRef.current?.play().catch(() => {
          // Autoplay blocked — user must click play
        });
      });

      hls.on(Events.ERROR, (_event: string, data: ErrorData) => {
        if (data.fatal) {
          setPlayerState("error");
          hls.destroy();
        }
      });
    } else if (videoRef.current.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari native HLS
      videoRef.current.src = streamUrl;
      setPlayerState("playing");
    } else {
      setPlayerState("error");
    }

    return () => {
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [streamUrl, isOnline]);

  // Destroy HLS on unmount
  useEffect(() => {
    return () => {
      hlsRef.current?.destroy();
    };
  }, []);

  const isLoadingState = tokenLoading || (isOnline && playerState === "loading");

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-surface",
        fullscreen ? "h-full w-full" : "aspect-video w-full",
        className,
      )}
    >
      {/* Video element — always in DOM so HLS can attach */}
      <video
        ref={videoRef}
        className={cn(
          "h-full w-full object-cover",
          playerState !== "playing" && "invisible",
        )}
        muted
        playsInline
        autoPlay
      />

      {/* Offline overlay */}
      {playerState === "offline" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface">
          <Camera className="h-8 w-8 text-gray-600" />
          <span className="text-sm text-gray-500">Camera offline</span>
          <CameraStatusBadge isOnline={false} pulse={false} />
        </div>
      )}

      {/* Loading overlay */}
      {isLoadingState && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface">
          <Loader2 className="h-6 w-6 animate-spin text-brand-400" />
        </div>
      )}

      {/* Error overlay */}
      {(playerState === "error" || tokenError) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface">
          <AlertTriangle className="h-7 w-7 text-severity-warning" />
          <span className="text-sm text-gray-400">Stream unavailable</span>
        </div>
      )}

      {/* Camera name + status overlay (bottom-left) */}
      {playerState === "playing" && (
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="truncate text-xs font-medium text-white">{camName}</span>
            <CameraStatusBadge isOnline={true} showLabel={false} />
          </div>
        </div>
      )}
    </div>
  );
}
