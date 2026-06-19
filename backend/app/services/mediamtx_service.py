"""
app/services/mediamtx_service.py
HTTP client for MediaMTX's REST management API.
All calls are best-effort — a failure here must NOT roll back the DB transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import MediaMTXError

if TYPE_CHECKING:
    from app.models.camera import camera_master

logger = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(10.0)


class MediaMTXService:
    """Wraps the MediaMTX v3 config paths API."""

    def __init__(self) -> None:
        self._base = settings.mediamtx_api_url.rstrip("/")

    def _build_path_config(self, cam: "camera_master") -> dict[str, Any]:
        """Build MediaMTX path config JSON for a camera."""
        strm_type = ""
        if cam.stream_type:
            strm_type = cam.stream_type.strm_type.upper()

        if strm_type == "RTSP":
            source = f"rtsp://{cam.cam_usrname}:{cam.cam_pass}@" f"{cam.cam_strm1.split('://')[-1]}"
        elif strm_type in ("RTMP", "RTSP CLOUD"):
            source = "publisher"
        else:
            source = cam.cam_strm1

        return {
            "name": cam.cam_id,
            "source": source,
            "record": True,
            "recordPath": f"/recordings/{cam.cam_id}/%Y/%m/%d/%H-%M-%S-%f-%path",
            "recordFormat": "fmp4",
            "recordPartDuration": "1s",
            "recordSegmentDuration": "20s",
        }

    async def add_path(self, cam: "camera_master") -> bool:
        """Register a camera stream path with MediaMTX. Returns True on success."""
        if not cam.cam_id:
            logger.warning("mediamtx.add_path.no_cam_id", cam_name=cam.cam_name)
            return False

        url = f"{self._base}/v3/config/paths/add/live/{cam.cam_id}"
        payload = self._build_path_config(cam)

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code in (200, 201):
                    logger.info("mediamtx.path_added", cam_id=cam.cam_id)
                    return True
                logger.warning(
                    "mediamtx.add_path_failed",
                    cam_id=cam.cam_id,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return False
        except httpx.RequestError as exc:
            logger.error("mediamtx.add_path_error", cam_id=cam.cam_id, error=str(exc))
            return False

    async def delete_path(self, cam_id: str) -> bool:
        """Remove a camera stream path from MediaMTX. Returns True on success."""
        url = f"{self._base}/v3/config/paths/delete/live/{cam_id}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.delete(url)
                if resp.status_code in (200, 204):
                    logger.info("mediamtx.path_deleted", cam_id=cam_id)
                    return True
                logger.warning(
                    "mediamtx.delete_path_failed",
                    cam_id=cam_id,
                    status=resp.status_code,
                )
                return False
        except httpx.RequestError as exc:
            logger.error("mediamtx.delete_path_error", cam_id=cam_id, error=str(exc))
            return False

    async def get_active_paths(self) -> list[dict[str, Any]]:
        """
        Fetch all active stream paths from MediaMTX.
        Returns empty list on error rather than raising.
        """
        url = f"{self._base}/v3/paths/list"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                return data.get("items", [])
        except Exception as exc:
            logger.error("mediamtx.get_paths_error", error=str(exc))
            return []

    async def get_path(self, cam_id: str) -> dict[str, Any] | None:
        """Get info for a single stream path. Returns None if not found."""
        url = f"{self._base}/v3/paths/get/live/{cam_id}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("mediamtx.get_path_error", cam_id=cam_id, error=str(exc))
            return None
