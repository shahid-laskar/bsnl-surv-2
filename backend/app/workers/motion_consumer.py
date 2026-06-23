"""
workers/motion_consumer/main.py — Phase 5, rewritten against BaseKafkaConsumer.

Replaces the previous standalone implementation (sync kafka-python +
requests, hand-rolled retry/DLQ loop) with a thin subclass of
BaseKafkaConsumer. All retry, DLQ, manual-commit, health-endpoint, and
SIGTERM logic now lives in base_consumer.py exactly once — this file
only contains domain logic: "what does processing a motion event mean."

Behavior preserved from the original file:
  - Posts to FastAPI /api/v1/cameras/{camera_id}/motion-event
  - Falls back to Django URL if FASTAPI_URL env var points there instead
    (kept as a constructor-level config value, not hardcoded)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from workers.base_consumer import BaseKafkaConsumer, KafkaEvent

TOPIC = "camera.motion"
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "motion-event-consumers")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))
FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")
HTTP_TIMEOUT = httpx.Timeout(10.0)


class MotionEventConsumer(BaseKafkaConsumer):
    default_event_type = "camera.motion"

    def __init__(self) -> None:
        super().__init__(topic=TOPIC, group_id=GROUP_ID, health_port=HEALTH_PORT)
        self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

    async def process(self, event: KafkaEvent) -> None:
        payload: dict[str, Any] = event.payload
        camera_id = payload["camera_id"]

        resp = await self._client.post(
            f"{FASTAPI_URL}/api/v1/cameras/{camera_id}/motion-event",
            json={
                "camera_id": camera_id,
                "is_motion": payload["is_motion"],
                "timestamp": payload["timestamp"],
            },
        )
        resp.raise_for_status()

    async def _shutdown(self) -> None:
        await self._client.aclose()
        await super()._shutdown()


async def main() -> None:
    consumer = MotionEventConsumer()
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
