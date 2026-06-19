"""
workers/status_monitor.py — Phase 5 reliability fix.

Consumes camera.status Kafka topic and posts to FastAPI /api/v1/camera-alerts.
Key changes:
  1. enable_auto_commit=False  → manual commit
  2. DLQ for failed messages
  3. Health endpoint port 8084
  4. Posts to FastAPI (not Django ORM directly)
  5. FCM push notifications (optional, fire-and-forget)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import requests
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("status_monitor")

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "status-monitors")
TOPIC = os.getenv("KAFKA_TOPIC_STATUS", "camera.status")
DLQ_TOPIC = f"{TOPIC}.dlq"
FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8084"))
MAX_RETRIES = 3


class _State:
    ok: int = 0
    failed: int = 0
    running: bool = True
    last_ok: float = time.time()


_s = _State()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(
            {
                "status": "ok" if _s.running else "stopped",
                "alerts_ok": _s.ok,
                "alerts_failed": _s.failed,
                "last_ok_seconds_ago": round(time.time() - _s.last_ok, 1),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


def _post_alert(event: dict[str, Any]) -> None:
    """Forward status event to FastAPI alert endpoint."""
    resp = requests.post(
        f"{FASTAPI_URL}/api/v1/camera-alerts",
        json={
            "camera": event.get("camera", ""),
            "status": event.get("status", ""),
            "timestamp": event.get("timestamp", time.time()),
        },
        timeout=10,
    )
    resp.raise_for_status()


def _send_fcm_notification(event: dict[str, Any]) -> None:
    """Fire-and-forget FCM push. Logs on failure, never raises."""
    if not FCM_SERVER_KEY:
        return
    try:
        cam = event.get("camera", "").removeprefix("live/")
        status = "UP" if event.get("status") == "ready" else "DOWN"
        ts = datetime.fromtimestamp(float(event.get("timestamp", time.time())), tz=timezone.utc)

        requests.post(
            "https://fcm.googleapis.com/fcm/send",
            json={
                "to": f"/topics/SARVANETRA_ALERTS",
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
            timeout=5,
        )
    except Exception as exc:
        logger.warning("fcm.failed", extra={"error": str(exc)})


class StatusMonitor:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_SERVERS,
            group_id=KAFKA_GROUP_ID,
            enable_auto_commit=False,
            auto_offset_reset="latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            max_poll_records=100,
            session_timeout_ms=30_000,
        )
        self._dlq = KafkaProducer(
            bootstrap_servers=KAFKA_SERVERS,
            value_serializer=lambda v: v,
            retries=3,
        )
        self._running = True

    def run(self) -> None:
        try:
            for message in self._consumer:
                if not self._running:
                    break

                event = message.value
                success = False

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        _post_alert(event)
                        success = True
                        break
                    except Exception as exc:
                        logger.warning(
                            "monitor.attempt_failed",
                            extra={"attempt": attempt, "error": str(exc)},
                        )
                        if attempt < MAX_RETRIES:
                            time.sleep(2**attempt)

                if success:
                    self._consumer.commit()
                    _s.ok += 1
                    _s.last_ok = time.time()
                    # Fire FCM in background thread — never blocks consumer
                    threading.Thread(
                        target=_send_fcm_notification,
                        args=(event,),
                        daemon=True,
                    ).start()
                else:
                    _s.failed += 1
                    dlq_msg = json.dumps(
                        {
                            "original": event,
                            "error": "max_retries_exceeded",
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).encode()
                    self._dlq.send(DLQ_TOPIC, dlq_msg)
                    self._dlq.flush()
                    self._consumer.commit()
                    logger.error("monitor.dlq_sent")
        finally:
            self._consumer.close()
            self._dlq.close()
            _s.running = False

    def stop(self) -> None:
        self._running = False


def main() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    monitor = StatusMonitor()

    def _sigterm(*_: Any) -> None:
        monitor.stop()

    signal.signal(signal.SIGTERM, _sigterm)
    monitor.run()


if __name__ == "__main__":
    main()
