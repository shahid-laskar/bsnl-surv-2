"""
app/models/base.py
SQLAlchemy 2.x declarative base used by all models.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models.
    All table names must be specified explicitly via __tablename__ to match
    existing Django-managed tables exactly.
    """

    type_annotation_map: dict[type, Any] = {
        datetime: DateTime(timezone=True),
    }

    def __repr__(self) -> str:
        """Generic repr — avoids triggering lazy-load of relationships."""
        pk_cols = [col.name for col in self.__table__.primary_key.columns]
        pk_vals = {col: getattr(self, col, None) for col in pk_cols}
        cls_name = type(self).__name__
        pk_str = ", ".join(f"{k}={v!r}" for k, v in pk_vals.items())
        return f"<{cls_name}({pk_str})>"


class TimestampMixin:
    """Adds created_at / updated_at to models that need them."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
