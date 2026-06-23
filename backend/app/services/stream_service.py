"""
app/services/stream_service.py
Stream token generation and HLS URL construction.

Stream tokens are short-lived JWTs (15 min) that allow the frontend
to access HLS streams via Nginx auth_request. This replaces the Django
validate_stream_token view.

Flow:
  1. Frontend calls GET /api/v1/cameras/{cam_id}/stream-token
  2. StreamService generates a JWT with cam_id + user_id + type=stream
  3. Frontend embeds the token in the HLS URL as ?token=<jwt>
  4. Nginx calls POST /api/v1/auth/validate-stream-token before serving
     each HLS segment — returns 200 if valid, 401 if not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import CameraNotFoundError, ForbiddenError
from app.core.security import create_stream_token, decode_stream_token
from app.models.camera import camera_master
from app.schemas.camera import StreamTokenResponse

logger = structlog.get_logger(__name__)


class StreamService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate_stream_token(
        self,
        cam_id: str,
        user_id: int,
        user_com_id: int | None,
        user_role: str,
    ) -> StreamTokenResponse:
        """
        Generate a short-lived stream token for the given camera.

        Verifies:
          - Camera exists and is active
          - User has permission to view this camera (role-scoped)

        Returns StreamTokenResponse with token + HLS URL + expiry.
        """
        cam = await self._get_active_camera(cam_id)

        # Scope check: cust_admin / viewer are restricted to their company
        if user_role not in ("sysadmin", "circle_admin", "ba_admin"):
            if user_com_id is None or cam.com_id != user_com_id:
                raise ForbiddenError(f"You do not have access to camera '{cam_id}'")

        token = create_stream_token(cam_id=cam_id, user_id=user_id)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.jwt_stream_token_expire_minutes
        )
        stream_url = self._build_hls_url(cam_id, token)

        logger.info("stream.token_generated", cam_id=cam_id, user_id=user_id)

        return StreamTokenResponse(
            token=token,
            stream_url=stream_url,
            expires_at=expires_at,
            cam_id=cam_id,
        )

    def validate_stream_token(self, token: str) -> dict[str, Any]:
        """
        Validate a stream token. Raises UnauthorizedError on failure.
        Called by the /validate-stream-token endpoint (Nginx auth_request target).
        """
        return decode_stream_token(token)

    def get_hls_url(self, cam_id: str, token: str) -> str:
        """Build the full HLS URL including the stream token."""
        return self._build_hls_url(cam_id, token)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_active_camera(self, cam_id: str) -> camera_master:
        result = await self._db.execute(
            select(camera_master).where(
                camera_master.cam_id == cam_id,
                camera_master.is_active == True,  # noqa: E712
            )
        )
        cam = result.scalar_one_or_none()
        if cam is None:
            raise CameraNotFoundError(cam_id)
        return cam

    def _build_hls_url(self, cam_id: str, token: str) -> str:
        """
        Construct the HLS playlist URL served by Nginx → MediaMTX.
        Pattern: http://{domain}/stream/hls/live/{cam_id}/index.m3u8?token={token}
        """
        return (
            f"http://{settings.domain_name}"
            f"/stream/hls/live/{cam_id}/index.m3u8"
            f"?token={token}"
        )
