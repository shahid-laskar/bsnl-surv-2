"""
alembic/versions/0001_initial_schema.py

Initial migration: creates all tables with sv_ prefix and native FastAPI auth structure,
plus inserts seed data for BSNL circles, BAs, plans, stream types, and the initial admin.
"""

from __future__ import annotations

import os
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
import bcrypt

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def hash_password(plain_password: str) -> str:
    pw_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def upgrade() -> None:
    # 1. Circle Master
    op.create_table(
        "sv_circle_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cir_name", sa.String(length=100), nullable=False),
        sa.Column("cir_code", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cir_code"),
    )

    # 2. BA Master
    op.create_table(
        "sv_ba_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ba_name", sa.String(length=100), nullable=False),
        sa.Column("ba_code", sa.String(length=20), nullable=False),
        sa.Column("cir_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cir_id"], ["sv_circle_master.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ba_code", "cir_id"),
    )

    # 3. Plan Master
    op.create_table(
        "sv_plan_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_name", sa.String(length=100), nullable=False),
        sa.Column("cam_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. Customer Master
    op.create_table(
        "sv_customer_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("com_name", sa.String(length=255), nullable=False),
        sa.Column("com_adr", sa.Text(), nullable=False),
        sa.Column("gstn", sa.String(length=15), nullable=True),
        sa.Column("cir_id", sa.Integer(), nullable=False),
        sa.Column("ba_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cir_id"], ["sv_circle_master.id"]),
        sa.ForeignKeyConstraint(["ba_id"], ["sv_ba_master.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["sv_plan_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sv_customer_cir_id", "sv_customer_master", ["cir_id"])
    op.create_index("idx_sv_customer_ba_id", "sv_customer_master", ["ba_id"])

    # 5. Stream Master
    op.create_table(
        "sv_stream_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strm_type", sa.String(length=50), nullable=False),
        sa.Column("remark", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. Users (replaces auth_user + UserDetails)
    op.create_table(
        "sv_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("cir_id", sa.Integer(), nullable=True),
        sa.Column("ba_id", sa.Integer(), nullable=True),
        sa.Column("com_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("device_tokens", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "date_joined",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cir_id"], ["sv_circle_master.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ba_id"], ["sv_ba_master.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["com_id"], ["sv_customer_master.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_sv_users_username", "sv_users", ["username"])
    op.create_index("idx_sv_users_email", "sv_users", ["email"])
    op.create_index(
        "idx_sv_users_com_id",
        "sv_users",
        ["com_id"],
        postgresql_where=sa.text("com_id IS NOT NULL"),
    )
    op.create_index(
        "idx_sv_users_cir_id",
        "sv_users",
        ["cir_id"],
        postgresql_where=sa.text("cir_id IS NOT NULL"),
    )
    op.create_index("idx_sv_users_role", "sv_users", ["role"])
    op.create_index("idx_sv_users_is_active", "sv_users", ["is_active"])

    # 7. Kong Consumers
    op.create_table(
        "sv_kong_consumers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kong_consumer_username", sa.String(length=255), nullable=False),
        sa.Column("jwt_key", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["sv_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("kong_consumer_username"),
        sa.UniqueConstraint("jwt_key"),
    )
    op.create_index("idx_sv_kong_consumers_user_id", "sv_kong_consumers", ["user_id"])
    op.create_index("idx_sv_kong_consumers_jwt_key", "sv_kong_consumers", ["jwt_key"])

    # 8. Refresh Tokens
    op.create_table(
        "sv_refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["sv_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_sv_refresh_tokens_user_id", "sv_refresh_tokens", ["user_id"])
    op.create_index("idx_sv_refresh_tokens_token_hash", "sv_refresh_tokens", ["token_hash"])
    op.create_index("idx_sv_refresh_tokens_expires_at", "sv_refresh_tokens", ["expires_at"])

    # 9. Device Master
    op.create_table(
        "sv_device_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=50), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("password", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("staging_status", sa.String(length=50), nullable=True),
        sa.Column("status_log", sa.String(length=500), nullable=True),
        sa.Column("dev_name", sa.String(length=300), nullable=True),
        sa.Column("dev_loc", sa.String(length=300), nullable=True),
        sa.Column("mqtt_status", sa.String(length=50), nullable=True),
        sa.Column("mqtt_update", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 10. Camera Master
    op.create_table(
        "sv_camera_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cam_id", sa.String(length=50), nullable=True),
        sa.Column("cam_name", sa.String(length=100), nullable=False),
        sa.Column("cam_loc", sa.String(length=300), nullable=False),
        sa.Column("cam_make", sa.String(length=100), nullable=False),
        sa.Column("cam_usrname", sa.String(length=100), nullable=False),
        sa.Column("cam_pass", sa.String(length=100), nullable=False),
        sa.Column("cam_strm1", sa.String(length=100), nullable=False),
        sa.Column("cam_strm2", sa.String(length=100), nullable=True),
        sa.Column("cam_strm3", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("motion_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cam_onvif", sa.Integer(), nullable=True),
        sa.Column(
            "upd_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("cir_id", sa.Integer(), nullable=False),
        sa.Column("ba_id", sa.Integer(), nullable=False),
        sa.Column("com_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=False),
        sa.Column("strm_type_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cir_id"], ["sv_circle_master.id"]),
        sa.ForeignKeyConstraint(["ba_id"], ["sv_ba_master.id"]),
        sa.ForeignKeyConstraint(["com_id"], ["sv_customer_master.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["sv_device_master.id"]),
        sa.ForeignKeyConstraint(["added_by"], ["sv_users.id"]),
        sa.ForeignKeyConstraint(["strm_type_id"], ["sv_stream_master.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cam_id"),
    )
    op.create_index("ix_camera_cam_id", "sv_camera_master", ["cam_id"])

    # 11. Video Segment
    op.create_table(
        "sv_video_segment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "minio_bucket", sa.String(length=100), nullable=False, server_default="recordings"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["sv_camera_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videosegment_camera_start", "sv_video_segment", ["camera_id", "start_time"])
    op.create_index("ix_videosegment_start_end", "sv_video_segment", ["start_time", "end_time"])

    # 12. Motion Event
    op.create_table(
        "sv_motion_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("motion_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motion_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["sv_camera_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_motion_camera_start", "sv_motion_event", ["camera_id", "motion_start"])
    op.create_index("ix_motion_camera_active", "sv_motion_event", ["camera_id", "is_active"])
    op.create_index("ix_motion_start_desc", "sv_motion_event", ["motion_start"])

    # 13. Motion Detection Health
    op.create_table(
        "sv_motion_detection_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "status_start",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["sv_camera_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mdhealth_camera_active", "sv_motion_detection_health", ["camera_id", "is_active"]
    )

    # 14. Camera Status Log
    op.create_table(
        "sv_camera_status_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("duration", sa.Interval(), nullable=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["sv_camera_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_statuslog_camera_ts", "sv_camera_status_log", ["camera_id", "timestamp"])

    # 15. Camera Health
    op.create_table(
        "sv_camera_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("current_status", sa.String(length=10), nullable=False),
        sa.Column(
            "last_change",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_downtime_duration", sa.Interval(), nullable=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["sv_camera_master.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("camera_id"),
    )

    # 16. API Log
    op.create_table(
        "sv_api_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("record_id", sa.String(length=50), nullable=True),
        sa.Column("record_name", sa.String(length=255), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("request_data", postgresql.JSONB(), nullable=True),
        sa.Column("response_data", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apilog_timestamp", "sv_api_log", ["timestamp"])

    # 17. Container Stats
    op.create_table(
        "sv_container_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("container_id", sa.String(length=64), nullable=False),
        sa.Column("container_name", sa.String(length=128), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("mem_percent", sa.Float(), nullable=False),
        sa.Column("mem_usage", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 18. Seed Initial Data
    # Seed circles
    op.execute("""
        INSERT INTO sv_circle_master (cir_name, cir_code) VALUES
        ('Kerala', 'KR')
        ON CONFLICT (cir_code) DO NOTHING;
    """)

    # Seed BAs
    op.execute("""
        INSERT INTO sv_ba_master (ba_name, ba_code, cir_id)
        SELECT 'Thiruvananthapuram', 'TVM', id FROM sv_circle_master WHERE cir_code = 'KR'
        ON CONFLICT (ba_code, cir_id) DO NOTHING;
    """)

    # Seed plans
    op.execute("""
        INSERT INTO sv_plan_master (plan_name, cam_limit) VALUES
        ('Starter',     10),
        ('Standard',    50),
        ('Enterprise', 200);
    """)

    # Seed stream types
    op.execute("""
        INSERT INTO sv_stream_master (strm_type, remark) VALUES
        ('RTSP',       'Direct RTSP pull from camera'),
        ('RTMP',       'RTMP push from camera to MediaMTX'),
        ('RTSP CLOUD', 'RTSP push via BSNL cloud relay')
        ON CONFLICT DO NOTHING;
    """)

    # Seed sysadmin user
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "ChangeMe@123")
    password_hash = hash_password(admin_password)

    op.execute(f"""
        INSERT INTO sv_users
          (username, email, first_name, last_name, password_hash, role, is_superuser)
        VALUES
          ('admin', 'admin@sarvanetra.local', 'System', 'Admin',
           '{password_hash}', 'sysadmin', TRUE)
        ON CONFLICT (username) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table("sv_container_stats")
    op.drop_table("sv_api_log")
    op.drop_table("sv_camera_health")
    op.drop_table("sv_camera_status_log")
    op.drop_table("sv_motion_detection_health")
    op.drop_table("sv_motion_event")
    op.drop_table("sv_video_segment")
    op.drop_table("sv_camera_master")
    op.drop_table("sv_device_master")
    op.drop_table("sv_refresh_tokens")
    op.drop_table("sv_kong_consumers")
    op.drop_table("sv_users")
    op.drop_table("sv_stream_master")
    op.drop_table("sv_customer_master")
    op.drop_table("sv_plan_master")
    op.drop_table("sv_ba_master")
    op.drop_table("sv_circle_master")
