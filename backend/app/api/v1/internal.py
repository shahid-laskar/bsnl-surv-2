"""
app/api/v1/internal.py
Internal webhooks for MediaMTX and Kafka workers.
No JWT auth required, protected by Nginx blocking external access.
"""

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.alert import CameraStatusLog
from app.models.camera import camera_master
from app.services.kafka_service import KafkaProducerService
from app.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


class StreamEventRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    path: str | None = None
    action: str | None = None
    actionDesc: str | None = None
    query: str | None = None


class RecordingCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    path: str
    duration: int | None = None


class CameraAlertRequest(BaseModel):
    cam_id: str
    status: str
    reason: str | None = None


@router.post("/stream-event", status_code=status.HTTP_200_OK)
async def handle_stream_event(
    event: StreamEventRequest,
) -> dict[str, str]:
    """MediaMTX reports stream ready/not-ready."""
    cam_id = event.name
    is_ready = event.action == "publish" or event.actionDesc == "publish"
    status_str = "up" if is_ready else "down"

    producer = KafkaProducerService()
    await producer.publish_camera_status(cam_id, status_str)

    logger.info("internal.stream_event_handled", cam_id=cam_id, status=status_str)
    return {"status": "ok"}


@router.post("/recording-complete", status_code=status.HTTP_200_OK)
async def handle_recording_complete(
    event: RecordingCompleteRequest,
) -> dict[str, str]:
    """MediaMTX reports new segment."""
    cam_id = event.name
    producer = KafkaProducerService()
    await producer.publish_recording_segment(cam_id, event.path)

    logger.info("internal.recording_complete_handled", cam_id=cam_id, path=event.path)
    return {"status": "ok"}


@router.post("/camera-alerts", status_code=status.HTTP_200_OK)
async def handle_camera_alerts(
    event: CameraAlertRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Workers report camera offline."""
    cam_id = event.cam_id

    result = await db.execute(select(camera_master).where(camera_master.cam_id == cam_id))
    cam = result.scalar_one_or_none()
    if not cam:
        logger.warning("internal.camera_alert_skipped", cam_id=cam_id, reason="camera_not_found")
        return {"status": "not_found"}

    status_log = CameraStatusLog(
        camera_id=cam.id,
        status=event.status,
    )
    db.add(status_log)
    await db.commit()

    if event.status == "down" and cam.cam_id:
        notifier = NotificationService()
        await notifier.send_camera_offline_alert(cam.cam_id, cam.cam_name, cam.com_id)

    logger.info("internal.camera_alert_handled", cam_id=cam_id, status=event.status)
    return {"status": "ok"}
