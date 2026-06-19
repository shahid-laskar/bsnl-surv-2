"""
app/api/v1/devices.py
Device and stream master management endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_role
from app.core.exceptions import DeviceNotFoundError
from app.models.device import device_master, stream_master
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/devices", tags=["devices"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    staging_status: str | None
    status_log: str | None
    dev_name: str | None
    dev_loc: str | None
    mqtt_status: str | None
    mqtt_update: datetime | None


class DeviceCaptureRequest(BaseModel):
    """Mobile app registers a new physical device (MQTT announce)."""

    device_no: str
    dev_name: str | None = None
    dev_loc: str | None = None
    timestamp: str | None = None


class DeviceStatusUpdateRequest(BaseModel):
    """MQTT online heartbeat from a device."""

    device_id: str
    timestamp: str | None = None


class StreamTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strm_type: str
    remark: str | None


# ── Device endpoints ──────────────────────────────────────────────────────────


@router.get("", response_model=list[DeviceResponse], summary="List devices")
async def list_devices(
    staging_status: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    q = select(device_master)
    if staging_status:
        q = q.where(device_master.staging_status == staging_status)
    result = await db.execute(q.order_by(device_master.id.desc()).limit(200))
    return [DeviceResponse.model_validate(d) for d in result.scalars().all()]


@router.post(
    "/capture",
    response_model=MessageResponse,
    summary="Register or update a device (called from mobile app / MQTT announce)",
)
async def capture_device(
    body: DeviceCaptureRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Upsert a device record by device_id.
    Called when a physical device powers on and sends an MQTT announcement.
    """
    result = await db.execute(
        select(device_master).where(device_master.device_id == body.device_no)
    )
    dev = result.scalar_one_or_none()

    if dev is None:
        dev = device_master(
            device_id=body.device_no,
            username="",
            password="",
            dev_name=body.dev_name,
            dev_loc=body.dev_loc,
            staging_status="NEW",
            status_log=body.timestamp,
        )
        db.add(dev)
    else:
        dev.dev_name = body.dev_name or dev.dev_name
        dev.dev_loc = body.dev_loc or dev.dev_loc
        dev.staging_status = "NEW"
        dev.status_log = body.timestamp

    await db.flush()
    return MessageResponse(message=f"Device {body.device_no} registered")


@router.post(
    "/status",
    response_model=MessageResponse,
    summary="Update device MQTT heartbeat status",
)
async def update_device_status(
    body: DeviceStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Called by the MQTT bridge to record a device heartbeat."""
    result = await db.execute(
        select(device_master).where(device_master.device_id == body.device_id)
    )
    dev = result.scalar_one_or_none()
    if dev is None:
        raise DeviceNotFoundError(body.device_id)

    dev.staging_status = "online"
    dev.status_log = body.timestamp
    await db.flush()
    return MessageResponse(message="Device status updated")


@router.get(
    "/stream-types",
    response_model=list[StreamTypeResponse],
    summary="List available stream types (RTSP, RTMP, RTSP CLOUD)",
)
async def list_stream_types(
    db: AsyncSession = Depends(get_db),
) -> list[StreamTypeResponse]:
    result = await db.execute(select(stream_master).order_by(stream_master.id))
    return [StreamTypeResponse.model_validate(s) for s in result.scalars().all()]
