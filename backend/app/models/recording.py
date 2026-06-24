"""
app/models/recording.py
VideoSegment — one recorded video segment stored in MinIO.

Bug fix from Django version:
  WRONG: self.camera.camera_id  (AttributeError)
  FIXED: self.camera.cam_id
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.camera import camera_master


class VideoSegment(Base):
    """
    A single recorded video segment — one fmp4 file in MinIO.
    Duration is stored in seconds (float).
    Django table: sv_videosegment
    """

    __tablename__ = "sv_video_segment"

    __table_args__ = (
        Index("ix_videosegment_camera_start", "camera_id", "start_time"),
        Index("ix_videosegment_start_end", "start_time", "end_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Time range
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False)  # seconds

    # Storage
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minio_bucket: Mapped[str] = mapped_column(String(100), nullable=False, default="recordings")

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Foreign key to camera — named `camera_id` to match Django ORM naming
    camera_id: Mapped[int] = mapped_column(ForeignKey("sv_camera_master.id"), nullable=False)

    # Relationship
    camera: Mapped["camera_master"] = relationship("camera_master", back_populates="segments")

    def __repr__(self) -> str:
        # Bug fix: Django version used self.camera.camera_id (AttributeError)
        # Correct field name is cam_id
        cam_id = self.camera.cam_id if self.camera else f"camera_id={self.camera_id}"
        return f"<VideoSegment(id={self.id!r}, cam_id={cam_id!r}, " f"start={self.start_time!r})>"

    @property
    def start_timestamp(self) -> int:
        """Unix timestamp of segment start."""
        return int(self.start_time.timestamp())

    @property
    def end_timestamp(self) -> int:
        """Unix timestamp of segment end."""
        return int(self.end_time.timestamp())
