"""
app/api/v1/alerts.py
API endpoints for camera alerts and health status.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import NotFoundError
from app.models.alert import CameraHealth, CameraStatusLog
from app.models.camera import camera_master
from app.schemas.alert import AlertListResponse, CameraAlertResponse, CameraHealthResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])
health_router = APIRouter(prefix="/cameras", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """Get paginated list of camera offline/online alerts."""
    query = select(CameraStatusLog).join(camera_master)

    if current_user.role not in ("sysadmin", "circle_admin", "ba_admin"):
        query = query.where(camera_master.com_id == current_user.com_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get items
    query = query.order_by(CameraStatusLog.timestamp.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    # Need camera names as well
    cam_ids = {item.camera_id for item in items}
    cam_names = {}
    if cam_ids:
        cam_res = await db.execute(select(camera_master.id, camera_master.cam_name).where(camera_master.id.in_(cam_ids)))
        cam_names = {row.id: row.cam_name for row in cam_res.all()}

    response_items = []
    for item in items:
        response_items.append(
            CameraAlertResponse(
                id=item.id,
                camera_id=item.camera_id,
                cam_name=cam_names.get(item.camera_id),
                status=item.status,
                timestamp=item.timestamp,
                duration=item.duration,
                acknowledged=item.acknowledged,
            )
        )

    return AlertListResponse(items=response_items, total=total)


@router.patch("/{alert_id}/acknowledge", response_model=CameraAlertResponse)
async def acknowledge_alert(
    alert_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CameraAlertResponse:
    """Mark an alert as acknowledged."""
    query = select(CameraStatusLog).join(camera_master).where(CameraStatusLog.id == alert_id)
    if current_user.role not in ("sysadmin", "circle_admin", "ba_admin"):
        query = query.where(camera_master.com_id == current_user.com_id)

    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise NotFoundError("Alert not found or access denied")

    alert.acknowledged = True
    await db.commit()
    await db.refresh(alert)
    
    # Get cam name
    cam_res = await db.execute(select(camera_master.cam_name).where(camera_master.id == alert.camera_id))
    cam_name = cam_res.scalar_one_or_none()
    
    resp = CameraAlertResponse.model_validate(alert)
    resp.cam_name = cam_name
    return resp


@health_router.get("/{cam_id}/health", response_model=CameraHealthResponse)
async def get_camera_health(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CameraHealthResponse:
    """Get the current health status of a specific camera."""
    query = select(CameraHealth).join(camera_master).where(camera_master.cam_id == cam_id)
    if current_user.role not in ("sysadmin", "circle_admin", "ba_admin"):
        query = query.where(camera_master.com_id == current_user.com_id)

    result = await db.execute(query)
    health = result.scalar_one_or_none()

    if not health:
        raise NotFoundError(f"Health status not found for camera {cam_id}")

    return CameraHealthResponse.model_validate(health)
