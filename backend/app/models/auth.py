# app/models/auth.py
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class SvUser(Base):
    __tablename__ = "sv_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    cir_id: Mapped[int | None] = mapped_column(
        ForeignKey("sv_circle_master.id", ondelete="SET NULL"), nullable=True
    )
    ba_id: Mapped[int | None] = mapped_column(
        ForeignKey("sv_ba_master.id", ondelete="SET NULL"), nullable=True
    )
    com_id: Mapped[int | None] = mapped_column(
        ForeignKey("sv_customer_master.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    device_tokens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    date_joined: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    kong_consumer: Mapped["SvKongConsumer | None"] = relationship(
        "SvKongConsumer", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["SvRefreshToken"]] = relationship(
        "SvRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"SvUser(id={self.id}, username={self.username!r}, role={self.role!r})"


class SvKongConsumer(Base):
    __tablename__ = "sv_kong_consumers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("sv_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    kong_consumer_username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    jwt_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["SvUser"] = relationship("SvUser", back_populates="kong_consumer")


class SvRefreshToken(Base):
    __tablename__ = "sv_refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("sv_users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["SvUser"] = relationship("SvUser", back_populates="refresh_tokens")
