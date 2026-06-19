"""
app/models/motion.py
motion_event and MotionDetectionHealth.
Django table names preserved exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.camera import camera_master


class motion_event(Base):
    """
    A single motion detection event with start and optional end timestamp.
    When is_active=True, motion is currently ongoing.
    Django table: sv_motion_events  (note: custom table name set in Django Meta)
    """

    __tablename__ = "sv_motion_events"

    __table_args__ = (
        Index("ix_motion_camera_start", "camera_id", "motion_start"),
        Index("ix_motion_camera_active", "camera_id", "is_active"),
        Index("ix_motion_start_desc", "motion_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    motion_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    motion_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # FK uses camera integer PK (named camera_id to match Django ORM)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("sv_camera_master.id"), nullable=False, index=True
    )

    # Relationship
    camera: Mapped["camera_master"] = relationship("camera_master", back_populates="motion_events")

    @property
    def duration_seconds(self) -> float | None:
        """Duration of the motion event in seconds. None if still active."""
        if self.motion_end is None:
            return None
        return (self.motion_end - self.motion_start).total_seconds()

    def __repr__(self) -> str:
        cam_id = self.camera.cam_id if self.camera else f"camera_id={self.camera_id}"
        return (
            f"<motion_event(id={self.id!r}, cam_id={cam_id!r}, "
            f"motion_start={self.motion_start!r}, is_active={self.is_active!r})>"
        )


class MotionDetectionHealth(Base):
    """
    Tracks per-camera ONVIF subscription uptime/downtime periods.
    Django table: sv_motiondetectionhealth
    """

    __tablename__ = "sv_motiondetectionhealth"

    __table_args__ = (
        Index("ix_mdhealth_camera_active", "camera_id", "is_active"),
        Index("ix_mdhealth_status_start", "status", "status_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    status: Mapped[str] = mapped_column(String(10), nullable=False)  # "UP" | "DOWN"
    status_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # FK
    camera_id: Mapped[int] = mapped_column(ForeignKey("sv_camera_master.id"), nullable=False)

    # Relationship
    camera: Mapped["camera_master"] = relationship("camera_master", back_populates="motion_health")

    def __repr__(self) -> str:
        return (
            f"<MotionDetectionHealth(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"status={self.status!r}, is_active={self.is_active!r})>"
        )
