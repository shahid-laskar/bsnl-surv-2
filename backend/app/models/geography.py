"""
app/models/geography.py
circle_master and ba_master — the top-level BSNL geographic hierarchy.
Table names match existing Django migrations exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import customer_master
    from app.models.camera import camera_master
    from app.models.auth import SvUser


class circle_master(Base):
    """
    Top-level geographic unit (e.g., Kerala Circle).
    Table: sv_circle_master
    """

    __tablename__ = "sv_circle_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cir_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cir_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    # Relationships
    bas: Mapped[list["ba_master"]] = relationship(
        "ba_master", back_populates="circle", lazy="selectin"
    )
    customers: Mapped[list["customer_master"]] = relationship(
        "customer_master", back_populates="circle"
    )
    cameras: Mapped[list["camera_master"]] = relationship("camera_master", back_populates="circle")

    def __repr__(self) -> str:
        return f"<circle_master(id={self.id!r}, cir_name={self.cir_name!r}, cir_code={self.cir_code!r})>"


class ba_master(Base):
    """
    Business Area — child of circle_master.
    Table: sv_ba_master
    """

    __tablename__ = "sv_ba_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ba_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ba_code: Mapped[str] = mapped_column(String(20), nullable=False)
    cir_id: Mapped[int] = mapped_column(
        ForeignKey("sv_circle_master.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    circle: Mapped["circle_master"] = relationship("circle_master", back_populates="bas")
    customers: Mapped[list["customer_master"]] = relationship(
        "customer_master", back_populates="ba"
    )
    cameras: Mapped[list["camera_master"]] = relationship("camera_master", back_populates="ba")

    def __repr__(self) -> str:
        return f"<ba_master(id={self.id!r}, ba_name={self.ba_name!r}, ba_code={self.ba_code!r})>"
