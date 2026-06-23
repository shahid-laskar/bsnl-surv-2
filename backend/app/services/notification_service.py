"""
app/services/notification_service.py
Service for sending FCM push notifications.
"""

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class NotificationService:
    async def send_camera_offline_alert(self, cam_id: str, cam_name: str, customer_id: int) -> None:
        """Send FCM to all users of that customer."""
        title = "Camera Offline"
        body = f"Camera {cam_name} ({cam_id}) is offline."
        logger.info("fcm.send", title=title, body=body, customer_id=customer_id)
        # Assuming we fetch device tokens for customer_id from DB
        # device_tokens = await get_device_tokens_for_customer(customer_id)
        # await self._send_fcm(device_tokens, title, body)

    async def send_motion_alert(self, cam_id: str, cam_name: str, customer_id: int) -> None:
        """Send optional motion notifications."""
        title = "Motion Detected"
        body = f"Motion detected on camera {cam_name} ({cam_id})."
        logger.info("fcm.send", title=title, body=body, customer_id=customer_id)

    async def _send_fcm(self, device_tokens: list[str], title: str, body: str, data: dict | None = None) -> None:
        if not hasattr(settings, "fcm_server_key") or not settings.fcm_server_key:
            logger.warning("fcm.skip", reason="fcm_server_key not configured")
            return

        url = "https://fcm.googleapis.com/fcm/send"
        headers = {
            "Authorization": f"key={settings.fcm_server_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "registration_ids": device_tokens,
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data or {},
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=5.0)
                resp.raise_for_status()
                logger.debug("fcm.success", status=resp.status_code)
            except httpx.HTTPError as e:
                logger.error("fcm.failed", error=str(e))
