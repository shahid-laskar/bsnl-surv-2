"""
workers/status_monitor/main.py — Phase 5, rewritten against BaseKafkaConsumer.

Domain logic only: forward camera.status events to FastAPI, then fire
an FCM push notification. FCM is intentionally NOT part of the retry
path — base_consumer's retry/DLQ logic governs the FastAPI POST only,
exactly like the original file (FCM failures are logged, never raised,
never cause a DLQ entry).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from workers.base_consumer import BaseKafkaConsumer, KafkaEvent

TOPIC = os.getenv("KAFKA_TOPIC_STATUS", "camera.status")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "status-monitors")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8084"))
FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
HTTP_TIMEOUT = httpx.Timeout(10.0)


class StatusMonitor(BaseKafkaConsumer):
    default_event_type = "camera.status"

    def __init__(self) -> None:
        super().__init__(topic=TOPIC, group_id=GROUP_ID, health_port=HEALTH_PORT)
        self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

    async def process(self, event: KafkaEvent) -> None:
        payload: dict[str, Any] = event.payload

        resp = await self._client.post(
            f"{FASTAPI_URL}/api/v1/camera-alerts",
            json={
                "camera": payload.get("camera", payload.get("camera_id", "")),
                "status": payload.get("status", ""),
                "timestamp": payload.get("timestamp"),
            },
        )
        resp.raise_for_status()

        # Fire-and-forget — never affects commit/retry/DLQ outcome.
        asyncio.create_task(self._send_fcm_notification(payload))

    async def _send_fcm_notification(self, payload: dict[str, Any]) -> None:
        if not FCM_SERVER_KEY:
            return
        try:
            cam = str(payload.get("camera", payload.get("camera_id", ""))).removeprefix("live/")
            status = "UP" if payload.get("status") == "ready" else "DOWN"
            raw_ts = payload.get("timestamp", datetime.now(timezone.utc).timestamp())
            ts = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)

            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as fcm_client:
                await fcm_client.post(
                    "https://fcm.googleapis.com/fcm/send",
                    json={
                        "to": "/topics/SARVANETRA_ALERTS",
                        "notification": {
                            "title": f"Camera {cam} is {status}",
                            "body": ts.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        },
                        "data": {"cam_id": cam, "status": status},
                    },
                    headers={
                        "Authorization": f"key={FCM_SERVER_KEY}",
                        "Content-Type": "application/json",
                    },
                )
        except Exception as exc:
            self.logger.warning(f"fcm.failed error={exc}")

    async def _shutdown(self) -> None:
        await self._client.aclose()
        await super()._shutdown()


async def main() -> None:
    monitor = StatusMonitor()
    await monitor.start()


if __name__ == "__main__":
    asyncio.run(main())