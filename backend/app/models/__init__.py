"""
app/models/__init__.py
Re-exports all models so Alembic's env.py can find them with a single import.
"""

from app.models.base import Base, TimestampMixin
from app.models.geography import circle_master, ba_master
from app.models.customer import plan_master, customer_master
from app.models.device import stream_master, device_master
from app.models.camera import camera_master
from app.models.recording import VideoSegment
from app.models.motion import motion_event, MotionDetectionHealth
from app.models.alert import CameraStatusLog, CameraHealth
from app.models.audit import ApiLog, ContainerStats
from app.models.auth import SvUser, SvKongConsumer, SvRefreshToken

__all__ = [
    "Base",
    "TimestampMixin",
    "circle_master",
    "ba_master",
    "plan_master",
    "customer_master",
    "stream_master",
    "device_master",
    "camera_master",
    "VideoSegment",
    "motion_event",
    "MotionDetectionHealth",
    "CameraStatusLog",
    "CameraHealth",
    "ApiLog",
    "ContainerStats",
    "SvUser",
    "SvKongConsumer",
    "SvRefreshToken",
]
