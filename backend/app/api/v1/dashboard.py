"""
app/api/v1/dashboard.py
Dashboard stats endpoint: active cameras, live streams, counts.
Role-scoped exactly as the existing Django dashboard_stats view.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.models.camera import camera_master
from app.models.customer import customer_master
from app.services.mediamtx_service import MediaMTXService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", summary="Get dashboard statistics (role-scoped)")
async def dashboard_stats(
    com_id: int | None = Query(default=None, description="Filter by company (cust_admin only)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns:
      - total_streams: cameras registered in DB for the scope
      - active_cameras: cam_ids with a live MediaMTX path (ready=True)
      - live_cameras: cam_ids with an active HLS reader
      - all_added_streams: total active cameras in DB
    """
    # Build base queryset based on role
    role = current_user.role

    if role == "sysadmin":
        base_q = select(camera_master).where(camera_master.is_active == True)  # noqa: E712
    elif role == "circle_admin":
        # Filter by circle via customer_master join
        cust_ids = select(customer_master.id).where(customer_master.cir_id == current_user.cir_id)
        base_q = select(camera_master).where(
            camera_master.is_active == True,  # noqa: E712
            camera_master.com_id.in_(cust_ids),
        )
    elif role in ("ba_admin",):
        cust_ids = select(customer_master.id).where(customer_master.ba_id == current_user.ba_id)
        base_q = select(camera_master).where(
            camera_master.is_active == True,  # noqa: E712
            camera_master.com_id.in_(cust_ids),
        )
    else:
        # cust_admin / viewer — use their com_id or the queried one
        effective_com = com_id or current_user.com_id
        base_q = select(camera_master).where(
            camera_master.is_active == True,  # noqa: E712
            camera_master.com_id == effective_com,
        )

    # Fetch all camera cam_ids in scope
    cam_result = await db.execute(base_q.with_only_columns(camera_master.cam_id))
    db_cam_ids: set[str] = {row[0] for row in cam_result.all() if row[0]}

    # Total DB cameras in scope
    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    all_count = count_result.scalar_one()

    # Fetch live state from MediaMTX
    mtx = MediaMTXService()
    paths = await mtx.get_active_paths()

    active_cams: list[str] = []
    live_cams: list[str] = []

    for item in paths:
        path_cam_id = item.get("name", "").split("/")[-1]
        if path_cam_id not in db_cam_ids:
            continue  # Not in this user's scope

        if item.get("ready") is True:
            active_cams.append(path_cam_id)

        readers = item.get("readers", [])
        if any(r.get("type") == "hlsMuxer" for r in readers):
            live_cams.append(path_cam_id)

    return {
        "total_streams": len(active_cams),
        "all_added_streams": all_count,
        "active_cameras": active_cams,
        "live_cameras": live_cams,
    }
