"""
app/models/camera.py
camera_master — the core camera entity.

cam_id generation: The Django `save()` override had a race condition.
In this implementation, cam_id is generated in CameraService.create()
inside a SELECT FOR UPDATE transaction. The model itself is passive.

Table name: sv_camera_master (preserves Django migration history).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.geography import circle_master, ba_master
    from app.models.customer import customer_master
    from app.models.device import device_master, stream_master
    from app.models.recording import VideoSegment
    from app.models.motion import motion_event, MotionDetectionHealth
    from app.models.alert import CameraStatusLog, CameraHealth


class camera_master(Base):
    """
    Physical IP camera.

    cam_id format: CAM{cir_code}{ba_code}{NNNNN}
    Example:       CAMKLTVM00001

    cam_id is NOT generated here — see CameraService._generate_cam_id()
    which uses SELECT FOR UPDATE to prevent race conditions.
    """

    __tablename__ = "sv_camera_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business key — auto-generated, unique
    cam_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Camera metadata
    cam_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_loc: Mapped[str] = mapped_column(String(300), nullable=False)
    cam_make: Mapped[str] = mapped_column(String(100), nullable=False)

    # Credentials (stored as-is; Phase 2 security hardening adds encryption)
    cam_usrname: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_pass: Mapped[str] = mapped_column(String(100), nullable=False)

    # Stream URLs
    cam_strm1: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_strm2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cam_strm3: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    motion_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ONVIF port (None if camera does not support ONVIF)
    cam_onvif: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Audit
    upd_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Foreign keys
    cir_id: Mapped[int] = mapped_column(ForeignKey("sv_circle_master.id"), nullable=False)
    ba_id: Mapped[int] = mapped_column(ForeignKey("sv_ba_master.id"), nullable=False)
    com_id: Mapped[int] = mapped_column(ForeignKey("sv_customer_master.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("sv_device_master.id"), nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("sv_users.id"), nullable=False)
    strm_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("sv_stream_master.id"), nullable=True
    )

    # Relationships
    circle: Mapped["circle_master"] = relationship(
        "circle_master", back_populates="cameras", lazy="selectin"
    )
    ba: Mapped["ba_master"] = relationship("ba_master", back_populates="cameras", lazy="selectin")
    customer: Mapped["customer_master"] = relationship(
        "customer_master", back_populates="cameras", lazy="selectin"
    )
    device: Mapped["device_master"] = relationship("device_master", back_populates="cameras")
    stream_type: Mapped["stream_master | None"] = relationship(
        "stream_master", back_populates="cameras", lazy="selectin"
    )
    segments: Mapped[list["VideoSegment"]] = relationship("VideoSegment", back_populates="camera")
    motion_events: Mapped[list["motion_event"]] = relationship(
        "motion_event", back_populates="camera"
    )
    motion_health: Mapped[list["MotionDetectionHealth"]] = relationship(
        "MotionDetectionHealth", back_populates="camera"
    )
    status_logs: Mapped[list["CameraStatusLog"]] = relationship(
        "CameraStatusLog", back_populates="camera"
    )
    health: Mapped["CameraHealth | None"] = relationship(
        "CameraHealth", back_populates="camera", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<camera_master(cam_id={self.cam_id!r}, cam_name={self.cam_name!r}, "
            f"is_active={self.is_active!r})>"
        )
