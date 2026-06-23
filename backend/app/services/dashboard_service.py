"""
app/services/dashboard_service.py
Dashboard stats and camera online/offline statuses.
Uses Redis to cache results for 30 seconds to avoid heavy DB queries on refresh.
"""

import json
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.redis import redis_client
from app.models.alert import CameraHealth
from app.models.camera import camera_master
from app.models.customer import customer_master
from app.models.motion import motion_event
from app.models.recording import VideoSegment
from app.services.mediamtx_service import MediaMTXService

logger = structlog.get_logger(__name__)


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._mtx = MediaMTXService()
        self._cache_ttl = 30  # seconds

    async def get_stats(self, user: CurrentUser) -> dict[str, Any]:
        """
        Get high-level stats for the dashboard.
        Results are cached in Redis per role/com_id for 30s.
        """
        cache_key = f"dashboard:stats:role_{user.role}:com_{user.com_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        stats = {
            "total_cameras": 0,
            "online_cameras": 0,
            "offline_cameras": 0,
            "active_motion_events": 0,
            "total_recordings": 0,
            "total_customers": 0,
        }

        is_admin = user.role in ("sysadmin", "circle_admin", "ba_admin")

        # Base queries
        cam_query = select(camera_master)
        cust_query = select(customer_master)
        health_query = select(CameraHealth.current_status).select_from(camera_master).outerjoin(
            CameraHealth, camera_master.id == CameraHealth.camera_id
        )
        motion_query = select(func.count()).select_from(motion_event).where(motion_event.is_active == True)
        rec_query = select(func.count()).select_from(VideoSegment)

        # Apply scope filtering
        if not is_admin:
            cam_query = cam_query.where(camera_master.com_id == user.com_id)
            cust_query = cust_query.where(customer_master.id == user.com_id)
            health_query = health_query.where(camera_master.com_id == user.com_id)
            motion_query = motion_query.join(camera_master, camera_master.id == motion_event.camera_id).where(camera_master.com_id == user.com_id)
            rec_query = rec_query.join(camera_master, camera_master.id == VideoSegment.camera_id).where(camera_master.com_id == user.com_id)

        # 1. Total cameras
        cam_count_res = await self._db.execute(select(func.count()).select_from(cam_query.subquery()))
        stats["total_cameras"] = cam_count_res.scalar() or 0

        # 2. Customers
        cust_count_res = await self._db.execute(select(func.count()).select_from(cust_query.subquery()))
        stats["total_customers"] = cust_count_res.scalar() or 0

        # 3. Online/Offline
        health_res = await self._db.execute(health_query)
        statuses = health_res.scalars().all()
        stats["online_cameras"] = statuses.count("up")
        stats["offline_cameras"] = len(statuses) - stats["online_cameras"]

        # 4. Motion Events
        motion_res = await self._db.execute(motion_query)
        stats["active_motion_events"] = motion_res.scalar() or 0

        # 5. Recordings
        rec_res = await self._db.execute(rec_query)
        stats["total_recordings"] = rec_res.scalar() or 0

        await redis_client.setex(cache_key, self._cache_ttl, json.dumps(stats))
        return stats

    async def get_camera_status(self, user: CurrentUser) -> list[dict[str, Any]]:
        """
        Get per-camera online/offline status.
        Results cached per role/com_id for 30s.
        """
        cache_key = f"dashboard:status:role_{user.role}:com_{user.com_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        query = select(camera_master.cam_id, camera_master.cam_name, CameraHealth.current_status).outerjoin(
            CameraHealth, camera_master.id == CameraHealth.camera_id
        )

        if user.role not in ("sysadmin", "circle_admin", "ba_admin"):
            query = query.where(camera_master.com_id == user.com_id)

        result = await self._db.execute(query)
        
        statuses = [
            {
                "cam_id": row.cam_id,
                "cam_name": row.cam_name,
                "status": row.current_status or "down"
            }
            for row in result.all()
            if row.cam_id is not None
        ]

        await redis_client.setex(cache_key, self._cache_ttl, json.dumps(statuses))
        return statuses
