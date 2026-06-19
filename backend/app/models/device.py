"""
app/models/device.py
device_master and stream_master — edge hardware and stream protocol models.
Table names match existing Django migrations exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.camera import camera_master


class stream_master(Base):
    """
    Stream type (RTSP, RTMP, RTSP CLOUD).
    Django table: sv_stream_master
    """

    __tablename__ = "sv_stream_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strm_type: Mapped[str] = mapped_column(String(50), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    cameras: Mapped[list["camera_master"]] = relationship(
        "camera_master", back_populates="stream_type"
    )

    def __repr__(self) -> str:
        return f"<stream_master(id={self.id!r}, strm_type={self.strm_type!r})>"


class device_master(Base):
    """
    Physical edge device (Raspberry Pi / NVR / bridge).
    Django table: sv_device_master
    """

    __tablename__ = "sv_device_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    password: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    staging_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_log: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dev_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dev_loc: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mqtt_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mqtt_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cameras: Mapped[list["camera_master"]] = relationship("camera_master", back_populates="device")

    def __repr__(self) -> str:
        return (
            f"<device_master(id={self.id!r}, device_id={self.device_id!r}, "
            f"staging_status={self.staging_status!r})>"
        )
