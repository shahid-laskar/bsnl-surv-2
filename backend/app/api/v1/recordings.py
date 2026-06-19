"""
app/api/v1/recordings.py
Recording endpoints: timeline query, segment video proxy, segment management.
"""

import re
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_role
from app.core.exceptions import MinIOError, NotFoundError
from app.core.minio import get_minio_client
from app.schemas.common import MessageResponse
from app.schemas.recording import (
    SegmentCreateRequest,
    SegmentResponse,
    TimelineResponse,
)
from app.services.recording_service import RecordingService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("/timeline/{cam_id}", response_model=TimelineResponse, summary="Get video timeline")
async def get_timeline(
    cam_id: str,
    start: datetime = Query(..., description="ISO datetime (timezone-aware or IST assumed)"),
    end: datetime = Query(...),
    include_motion: bool = Query(default=True),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """
    Return video segments in [start, end] with overlapping motion events.
    Used by the frontend timeline player.
    """
    service = RecordingService(db)
    return await service.get_timeline(
        cam_id=cam_id,
        start_dt=start,
        end_dt=end,
        include_motion=include_motion,
    )


@router.get(
    "/{segment_id}/video",
    summary="Stream a video segment with range request support",
)
async def serve_segment_video(
    segment_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Serve a video segment from MinIO with HTTP Range support for seeking.
    The response streams directly — no buffering in FastAPI memory.
    """
    service = RecordingService(db)
    seg = await service.get_segment(segment_id)

    minio: Minio = get_minio_client()
    try:
        stat = minio.stat_object(seg.minio_bucket, seg.file_path)
        file_size = stat.size or seg.file_size

        response = minio.get_object(seg.minio_bucket, seg.file_path)

        return StreamingResponse(
            response,
            media_type="video/mp4",
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache, must-revalidate",
            },
        )
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise NotFoundError(f"Video file not found for segment {segment_id}") from exc
        raise MinIOError(str(exc)) from exc


@router.get(
    "/{segment_id}/presigned-url",
    summary="Get a presigned URL to download a segment directly from MinIO",
)
async def get_presigned_url(
    segment_id: int,
    expires: int = Query(default=3600, ge=60, le=86400),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a time-limited presigned URL that the frontend can use to
    download a recording directly from MinIO without routing through FastAPI.
    """
    service = RecordingService(db)
    url = await service.get_presigned_url(segment_id, expires=expires)
    return {"url": url, "expires_in": expires}


@router.post(
    "/segments",
    response_model=SegmentResponse,
    status_code=201,
    summary="Register a new video segment (internal — called by upload_worker)",
)
async def create_segment(
    body: SegmentCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    """
    Internal endpoint called by the upload_worker after uploading a segment to MinIO.
    No auth required (internal Docker network only — Nginx blocks external access).
    """
    service = RecordingService(db)
    seg = await service.create_segment(body)

    cam_id = seg.camera.cam_id if seg.camera else None
    return SegmentResponse(
        id=seg.id,
        cam_id=cam_id,
        start_time=seg.start_time,
        end_time=seg.end_time,
        duration=seg.duration,
        file_path=seg.file_path,
        file_size=seg.file_size,
        minio_bucket=seg.minio_bucket,
        created_at=seg.created_at,
        start_timestamp=seg.start_timestamp,
        end_timestamp=seg.end_timestamp,
    )
