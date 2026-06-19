"""
app/api/v1/motion.py
Motion event endpoints and camera alert (status log) endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import CameraNotFoundError, NotFoundError
from app.models.alert import CameraHealth, CameraStatusLog
from app.models.camera import camera_master
from app.models.motion import motion_event
from app.schemas.common import MessageResponse, PaginatedResponse
from pydantic import BaseModel, ConfigDict
from datetime import timedelta

router = APIRouter(tags=["motion"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class MotionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    motion_start: datetime
    motion_end: datetime | None
    is_active: bool
    duration_seconds: float | None


class CameraAlertRequest(BaseModel):
    """Payload from MediaMTX webhook (camera_ready.sh / camera_down.sh via Kafka status_monitor)."""

    camera: str  # cam_id (may include 'live/' prefix)
    status: str  # 'ready' | 'notReady'
    timestamp: float | str  # epoch or ISO string


class CameraAlertResponse(BaseModel):
    message: str
    cam_id: str
    status: str


# ── Motion event endpoints ────────────────────────────────────────────────────


@router.get(
    "/cameras/{cam_id}/motion",
    response_model=PaginatedResponse[MotionEventResponse],
    tags=["motion"],
    summary="List motion events for a camera",
)
async def list_motion_events(
    cam_id: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MotionEventResponse]:
    cam_result = await db.execute(select(camera_master).where(camera_master.cam_id == cam_id))
    cam = cam_result.scalar_one_or_none()
    if cam is None:
        raise CameraNotFoundError(cam_id)

    q = select(motion_event).where(motion_event.camera_id == cam.id)
    if start:
        q = q.where(motion_event.motion_start >= start)
    if end:
        q = q.where(motion_event.motion_start <= end)
    if is_active is not None:
        q = q.where(motion_event.is_active == is_active)

    from sqlalchemy import func, select as _select

    count_q = _select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        q.order_by(motion_event.motion_start.desc()).offset(offset).limit(page_size)
    )
    items = [MotionEventResponse.model_validate(m) for m in result.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


# ── Camera alert (status) endpoints ──────────────────────────────────────────


@router.post(
    "/camera-alerts",
    response_model=CameraAlertResponse,
    tags=["alerts"],
    summary="Ingest camera status event (ready/notReady)",
)
async def camera_alert(
    body: CameraAlertRequest,
    db: AsyncSession = Depends(get_db),
) -> CameraAlertResponse:
    """
    Called by the status_monitor Kafka consumer after consuming camera.status events.
    Records the status change and updates the CameraHealth snapshot.
    """
    from app.core.config import settings
    import pytz

    IST = pytz.timezone("Asia/Kolkata")

    cam_id = body.camera.removeprefix("live/")

    cam_result = await db.execute(select(camera_master).where(camera_master.cam_id == cam_id))
    cam = cam_result.scalar_one_or_none()
    if cam is None:
        raise CameraNotFoundError(cam_id)

    # Parse timestamp
    if isinstance(body.timestamp, (int, float)):
        from datetime import UTC

        ts = datetime.fromtimestamp(float(body.timestamp), tz=UTC)
    else:
        from datetime import datetime as _dt

        ts = _dt.fromisoformat(body.timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.UTC)

    # Normalise status
    status = "up" if body.status == "ready" else "down"

    # Fetch previous log to fill duration
    prev_result = await db.execute(
        select(CameraStatusLog)
        .where(CameraStatusLog.camera_id == cam.id)
        .order_by(CameraStatusLog.timestamp.desc())
        .limit(1)
    )
    prev_log = prev_result.scalar_one_or_none()

    # Append new log entry
    new_log = CameraStatusLog(camera_id=cam.id, status=status, timestamp=ts)
    db.add(new_log)

    # Fill duration on previous entry
    if prev_log and prev_log.duration is None:
        prev_log.duration = ts - prev_log.timestamp

    # Update / create health snapshot
    health_result = await db.execute(select(CameraHealth).where(CameraHealth.camera_id == cam.id))
    health = health_result.scalar_one_or_none()
    if health is None:
        health = CameraHealth(camera_id=cam.id, current_status=status, last_change=ts)
        db.add(health)
    else:
        if status == "up" and health.current_status == "down":
            health.last_downtime_duration = ts - health.last_change
        health.current_status = status
        health.last_change = ts

    await db.flush()

    return CameraAlertResponse(
        message="Camera status logged",
        cam_id=cam_id,
        status=status,
    )


@router.get(
    "/cameras/{cam_id}/health",
    tags=["alerts"],
    summary="Get current camera health snapshot",
)
async def get_camera_health(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cam_result = await db.execute(select(camera_master).where(camera_master.cam_id == cam_id))
    cam = cam_result.scalar_one_or_none()
    if cam is None:
        raise CameraNotFoundError(cam_id)

    health_result = await db.execute(select(CameraHealth).where(CameraHealth.camera_id == cam.id))
    health = health_result.scalar_one_or_none()

    if health is None:
        return {"cam_id": cam_id, "current_status": "unknown", "last_change": None}

    return {
        "cam_id": cam_id,
        "current_status": health.current_status,
        "last_change": health.last_change.isoformat() if health.last_change else None,
        "last_downtime_duration_seconds": (
            health.last_downtime_duration.total_seconds() if health.last_downtime_duration else None
        ),
    }
