"""
app/services/kafka_service.py
Async Kafka producer for backend-initiated events.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

logger = structlog.get_logger(__name__)


class KafkaEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any]


class KafkaProducerService:
    _instance: "KafkaProducerService | None" = None
    _producer: AIOKafkaProducer | None = None

    def __new__(cls) -> "KafkaProducerService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._producer = None
        return cls._instance

    async def start(self) -> None:
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v.model_dump()).encode("utf-8"),
            )
            await self._producer.start()
            logger.info("kafka.producer_started")

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka.producer_stopped")

    async def publish(self, topic: str, event: KafkaEvent) -> None:
        if self._producer is None:
            logger.warning("kafka.producer_not_started", topic=topic, event_type=event.event_type)
            return

        try:
            await self._producer.send_and_wait(topic, value=event)
            logger.debug("kafka.published", topic=topic, event_type=event.event_type)
        except Exception as e:
            logger.error("kafka.publish_failed", topic=topic, error=str(e))

    async def publish_camera_status(self, cam_id: str, status: str) -> None:
        """Publish to camera.status topic."""
        event = KafkaEvent(
            event_id=str(uuid.uuid4()),
            event_type="camera_status_changed",
            payload={"cam_id": cam_id, "status": status},
        )
        await self.publish("camera.status", event)

    async def publish_motion_event(self, cam_id: str, is_motion: bool) -> None:
        """Publish to camera.motion topic."""
        event = KafkaEvent(
            event_id=str(uuid.uuid4()),
            event_type="motion_detected" if is_motion else "motion_cleared",
            payload={"cam_id": cam_id, "is_motion": is_motion},
        )
        await self.publish("camera.motion", event)

    async def publish_recording_segment(self, cam_id: str, file_path: str) -> None:
        """Publish to recording.segments topic."""
        event = KafkaEvent(
            event_id=str(uuid.uuid4()),
            event_type="recording_segment_ready",
            payload={"cam_id": cam_id, "file_path": file_path},
        )
        await self.publish("recording.segments", event)
