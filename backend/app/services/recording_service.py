"""
app/services/recording_service.py
Business logic for VideoSegment timeline queries and segment CRUD.
"""

from __future__ import annotations

from datetime import datetime

import pytz
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import CameraNotFoundError, NotFoundError
from app.core.minio import generate_presigned_url
from app.models.camera import camera_master
from app.models.motion import motion_event
from app.models.recording import VideoSegment
from app.schemas.recording import (
    MotionEventData,
    SegmentCreateRequest,
    TimelineResponse,
    TimelineSegmentData,
)

logger = structlog.get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")


class RecordingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_segment(self, segment_id: int) -> VideoSegment:
        result = await self._db.execute(
            select(VideoSegment)
            .where(VideoSegment.id == segment_id)
            .options(selectinload(VideoSegment.camera))
        )
        seg = result.scalar_one_or_none()
        if seg is None:
            raise NotFoundError(f"Segment {segment_id} not found")
        return seg

    async def create_segment(self, data: SegmentCreateRequest) -> VideoSegment:
        """
        Called by the upload_worker (via internal API) after uploading to MinIO.
        Resolves cam_id → camera PK before inserting.
        """
        cam_result = await self._db.execute(
            select(camera_master).where(camera_master.cam_id == data.cam_id)
        )
        cam = cam_result.scalar_one_or_none()
        if cam is None:
            raise CameraNotFoundError(data.cam_id)

        seg = VideoSegment(
            camera_id=cam.id,
            start_time=data.start_time,
            end_time=data.end_time,
            duration=data.duration,
            file_path=data.file_path,
            file_size=data.file_size,
            minio_bucket=data.minio_bucket,
        )
        self._db.add(seg)
        await self._db.flush()
        logger.info(
            "recording.segment_created",
            segment_id=seg.id,
            cam_id=data.cam_id,
            duration=data.duration,
        )
        return seg

    async def get_presigned_url(self, segment_id: int, expires: int = 3600) -> str:
        """Generate a time-limited presigned URL for a segment file."""
        seg = await self.get_segment(segment_id)
        return generate_presigned_url(
            object_name=seg.file_path,
            bucket=seg.minio_bucket,
            expires_seconds=expires,
        )

    async def get_timeline(
        self,
        cam_id: str,
        start_dt: datetime,
        end_dt: datetime,
        include_motion: bool = True,
    ) -> TimelineResponse:
        """
        Build a timeline response: segments overlapping [start_dt, end_dt]
        with their overlapping motion events.
        Datetimes must be timezone-aware. If naive, IST is assumed.
        """
        # Ensure timezone awareness — assume IST if naive
        if start_dt.tzinfo is None:
            start_dt = IST.localize(start_dt)
        if end_dt.tzinfo is None:
            end_dt = IST.localize(end_dt)

        cam_result = await self._db.execute(
            select(camera_master).where(camera_master.cam_id == cam_id)
        )
        cam = cam_result.scalar_one_or_none()
        if cam is None:
            raise CameraNotFoundError(cam_id)

        # Fetch segments in range
        seg_result = await self._db.execute(
            select(VideoSegment)
            .where(
                VideoSegment.camera_id == cam.id,
                VideoSegment.start_time <= end_dt,
                VideoSegment.end_time >= start_dt,
            )
            .order_by(VideoSegment.start_time)
        )
        segments = seg_result.scalars().all()

        # Optionally fetch motion events
        motions: list[motion_event] = []
        if include_motion:
            motion_result = await self._db.execute(
                select(motion_event)
                .where(
                    motion_event.camera_id == cam.id,
                    motion_event.motion_start <= end_dt,
                    # Include active (no end) and ended events
                )
                .order_by(motion_event.motion_start)
            )
            all_motions = motion_result.scalars().all()
            # Filter: exclude motions that ended before our window
            motions = [m for m in all_motions if m.motion_end is None or m.motion_end >= start_dt]

        # Build timeline items
        timeline_segments: list[TimelineSegmentData] = []
        total_duration = 0.0
        cumulative = 0.0

        for seg in segments:
            seg_start_ist = seg.start_time.astimezone(IST)
            seg_end_ist = seg.end_time.astimezone(IST)

            # Find overlapping motions for this segment
            seg_motions: list[MotionEventData] = []
            if include_motion:
                for m in motions:
                    m_end = m.motion_end or end_dt
                    if seg.start_time < m_end and seg.end_time > m.motion_start:
                        m_start_ist = m.motion_start.astimezone(IST)
                        m_end_ist = m.motion_end.astimezone(IST) if m.motion_end else None
                        seg_motions.append(
                            MotionEventData(
                                id=m.id,
                                start=int(m.motion_start.timestamp()),
                                end=int(m.motion_end.timestamp()) if m.motion_end else None,
                                duration=m.duration_seconds,
                                is_active=m.is_active,
                                readable_start=m_start_ist.strftime("%H:%M:%S"),
                                readable_end=m_end_ist.strftime("%H:%M:%S")
                                if m_end_ist
                                else "Ongoing",
                            )
                        )

            item = TimelineSegmentData(
                id=seg.id,
                start_time=seg.start_timestamp,
                end_time=seg.end_timestamp,
                duration=seg.duration,
                cumulative_start=cumulative,
                cumulative_end=cumulative + seg.duration,
                url=f"/api/v1/recordings/{seg.id}/video",
                file_path=seg.file_path,
                readable_start=seg_start_ist.strftime("%H:%M:%S"),
                readable_end=seg_end_ist.strftime("%H:%M:%S"),
                motion_events=seg_motions,
                motion_count=len(seg_motions),
            )
            timeline_segments.append(item)
            total_duration += seg.duration
            cumulative += seg.duration

        return TimelineResponse(
            cam_id=cam_id,
            camera_name=cam.cam_name,
            segments=timeline_segments,
            total_duration=total_duration,
            segment_count=len(timeline_segments),
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
        )
