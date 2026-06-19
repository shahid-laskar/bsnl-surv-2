"""
app/schemas/recording.py + app/services/recording_service.py combined
Pydantic schemas and business logic for VideoSegment.
"""

# ── app/schemas/recording.py ──────────────────────────────────────────────────
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SegmentCreateRequest(BaseModel):
    """Called by the upload_worker after a segment lands in MinIO."""

    cam_id: str
    start_time: datetime
    end_time: datetime
    duration: float = Field(gt=0)
    file_path: str
    file_size: int = Field(gt=0)
    minio_bucket: str = "recordings"


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cam_id: str | None = None  # Resolved from relationship
    start_time: datetime
    end_time: datetime
    duration: float
    file_path: str
    file_size: int
    minio_bucket: str
    created_at: datetime
    start_timestamp: int
    end_timestamp: int


class TimelineRequest(BaseModel):
    cam_id: str
    start: datetime
    end: datetime
    include_motion: bool = True


class MotionEventData(BaseModel):
    id: int
    start: int
    end: int | None
    duration: float | None
    is_active: bool
    readable_start: str
    readable_end: str


class TimelineSegmentData(BaseModel):
    id: int
    start_time: int
    end_time: int
    duration: float
    cumulative_start: float
    cumulative_end: float
    url: str
    file_path: str
    readable_start: str
    readable_end: str
    motion_events: list[MotionEventData] = []
    motion_count: int = 0


class TimelineResponse(BaseModel):
    cam_id: str
    camera_name: str
    segments: list[TimelineSegmentData]
    total_duration: float
    segment_count: int
    start_date: str
    end_date: str
