"""
app/models/customer.py
plan_master and customer_master — BSNL billing/tenant hierarchy.
Table names match existing Django migrations exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.geography import circle_master, ba_master
    from app.models.camera import camera_master
    from app.models.auth import SvUser


class plan_master(Base):
    """
    Surveillance subscription plan — defines camera limits.
    Table: sv_plan_master
    """

    __tablename__ = "sv_plan_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Relationships
    customers: Mapped[list["customer_master"]] = relationship(
        "customer_master", back_populates="plan"
    )

    def __repr__(self) -> str:
        return (
            f"<plan_master(id={self.id!r}, plan_name={self.plan_name!r}, "
            f"cam_limit={self.cam_limit!r})>"
        )


class customer_master(Base):
    """
    Company / Customer — tenant-level entity.
    Table: sv_customer_master
    """

    __tablename__ = "sv_customer_master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    com_name: Mapped[str] = mapped_column(String(255), nullable=False)
    com_adr: Mapped[str] = mapped_column(String(500), nullable=False)
    gstn: Mapped[str | None] = mapped_column(String(15), nullable=True)

    # Foreign keys
    cir_id: Mapped[int] = mapped_column(ForeignKey("sv_circle_master.id"), nullable=False)
    ba_id: Mapped[int] = mapped_column(ForeignKey("sv_ba_master.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("sv_plan_master.id"), nullable=False)

    # Relationships
    circle: Mapped["circle_master"] = relationship("circle_master", back_populates="customers")
    ba: Mapped["ba_master"] = relationship("ba_master", back_populates="customers")
    plan: Mapped["plan_master"] = relationship("plan_master", back_populates="customers")
    cameras: Mapped[list["camera_master"]] = relationship(
        "camera_master", back_populates="customer"
    )

    def __repr__(self) -> str:
        return f"<customer_master(id={self.id!r}, com_name={self.com_name!r})>"
