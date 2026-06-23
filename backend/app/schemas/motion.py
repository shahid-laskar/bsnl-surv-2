"""
app/schemas/motion.py
Pydantic schemas for motion detection events.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MotionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    cam_name: str | None = None
    motion_start: datetime
    motion_end: datetime | None = None
    is_active: bool
    duration_seconds: int | None = None


class MotionEventListResponse(BaseModel):
    items: list[MotionEventResponse]
    total: int


class MotionHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    status: str
    status_start: datetime
    status_end: datetime | None = None
    failure_reason: str | None = None
