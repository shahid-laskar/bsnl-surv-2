"""
app/models/alert.py
CameraStatusLog and CameraHealth — camera online/offline tracking.

"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Interval, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.camera import camera_master


class CameraStatusLog(Base):
    """
    Append-only log of camera online/offline status changes.
    `duration` is filled when the next event arrives.
    Django table: sv_camerastatuslog
    """

    __tablename__ = "sv_camera_status_log"

    __table_args__ = (
        Index("ix_statuslog_camera_ts", "camera_id", "timestamp"),
        Index("ix_statuslog_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # "up" | "down"
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    duration: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # FK
    camera_id: Mapped[int] = mapped_column(ForeignKey("sv_camera_master.id"), nullable=False)

    # Relationship
    camera: Mapped["camera_master"] = relationship("camera_master", back_populates="status_logs")

    def __repr__(self) -> str:
        return (
            f"<CameraStatusLog(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"status={self.status!r}, timestamp={self.timestamp!r})>"
        )


class CameraHealth(Base):
    """
    Latest-value snapshot of a camera's health.
    One row per camera (OneToOne).
    Django table: sv_camerahealth
    """

    __tablename__ = "sv_camera_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    current_status: Mapped[str] = mapped_column(String(10), nullable=False)  # "up" | "down"
    last_change: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_downtime_duration: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)

    # FK (unique enforces OneToOne)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("sv_camera_master.id"), nullable=False, unique=True
    )

    # Relationship
    camera: Mapped["camera_master"] = relationship("camera_master", back_populates="health")

    def __repr__(self) -> str:
        return (
            f"<CameraHealth(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"current_status={self.current_status!r})>"
        )
