"""
app/schemas/alert.py
Pydantic V2 schemas for camera alerts and health status.
"""

from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict


class CameraAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    cam_name: str | None = None
    status: str
    timestamp: datetime
    duration: timedelta | None = None
    acknowledged: bool


class AlertListResponse(BaseModel):
    items: list[CameraAlertResponse]
    total: int


class AlertAcknowledgeRequest(BaseModel):
    alert_id: int


class CameraHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_status: str
    last_change: datetime
    last_downtime_duration: timedelta | None = None
