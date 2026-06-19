"""
app/models/audit.py
ApiLog and ContainerStats — operational audit and monitoring.
Django table names preserved exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ApiLog(Base):
    """
    Immutable log of every API call. Written once, never updated.
    Django table: sv_apilog
    """

    __tablename__ = "sv_apilog"

    __table_args__ = (
        Index("ix_apilog_timestamp", "timestamp"),
        Index("ix_apilog_method", "method"),
        Index("ix_apilog_endpoint", "endpoint"),
        Index("ix_apilog_user_id", "user_id"),
        Index("ix_apilog_status", "status"),
        Index("ix_apilog_client_ip", "client_ip"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    record_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # "success"|"error"
    request_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ApiLog(id={self.id!r}, method={self.method!r}, "
            f"endpoint={self.endpoint!r}, status={self.status!r})>"
        )


class ContainerStats(Base):
    """
    Point-in-time Docker container resource usage snapshot.
    Django table: sv_containerstats
    """

    __tablename__ = "sv_containerstats"

    __table_args__ = (Index("ix_containerstats_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    container_id: Mapped[str] = mapped_column(String(64), nullable=False)
    container_name: Mapped[str] = mapped_column(String(128), nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    mem_percent: Mapped[float] = mapped_column(Float, nullable=False)
    mem_usage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ContainerStats(container_name={self.container_name!r}, "
            f"cpu_percent={self.cpu_percent!r})>"
        )
