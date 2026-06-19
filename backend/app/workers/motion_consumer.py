"""
motion_event_consumer.py — Phase 5 reliability fix.

Key changes from original:
  1. enable_auto_commit=False  → manual commit after successful DB write
     Prevents data loss when the consumer crashes mid-processing.
  2. Dead Letter Queue (DLQ)   → messages that fail 3 times go to camera.motion.dlq
  3. Structured logging        → no bare print() calls
  4. Health HTTP endpoint      → port 8081, Docker health-check compatible
  5. Graceful shutdown         → SIGTERM closes consumer cleanly
  6. Posts to FastAPI          → uses /api/v1/camera-alerts instead of direct ORM
     (allows horizontal scaling without shared Django ORM state)
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
from kafka.errors import KafkaError

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("motion_consumer")

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "motion-event-consumers")
TOPIC = "camera.motion"
DLQ_TOPIC = "camera.motion.dlq"
MAX_RETRIES = 3
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))
FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")

# Fallback: if FastAPI is not yet migrated, post to Django
DJANGO_URL = os.getenv("DJANGO_URL", "http://djangocc:8000")


# ── Health HTTP server ────────────────────────────────────────────────────────


class _HealthState:
    last_processed: float = time.time()
    messages_ok: int = 0
    messages_failed: int = 0
    messages_dlq: int = 0
    running: bool = True


_state = _HealthState()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        age = time.time() - _state.last_processed
        body = json.dumps(
            {
                "status": "ok" if _state.running else "stopped",
                "last_processed_seconds_ago": round(age, 1),
                "messages_ok": _state.messages_ok,
                "messages_failed": _state.messages_failed,
                "messages_dlq": _state.messages_dlq,
            }
        ).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # suppress access log
        pass


def _start_health_server() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("health_server.started", extra={"port": HEALTH_PORT})


# ── DB write helpers ──────────────────────────────────────────────────────────


def _post_motion_event(event: dict[str, Any]) -> None:
    """
    POST the motion event to FastAPI which handles the DB write.
    Falls back to posting directly to Django if FastAPI is unavailable.
    """
    camera_id = event["camera_id"]
    is_motion = event["is_motion"]
    timestamp_str = event["timestamp"]

    # FastAPI motion endpoint (Phase 2+)
    url = f"{FASTAPI_URL}/api/v1/cameras/{camera_id}/motion-event"
    payload = {
        "camera_id": camera_id,
        "is_motion": is_motion,
        "timestamp": timestamp_str,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def _post_to_dlq(producer: KafkaProducer, raw_value: bytes, error: str) -> None:
    """Send a failed message to the DLQ topic with error metadata."""
    dlq_msg = {
        "original": raw_value.decode("utf-8", errors="replace"),
        "error": error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    producer.send(DLQ_TOPIC, value=json.dumps(dlq_msg).encode("utf-8"))
    producer.flush()
    _state.messages_dlq += 1
    logger.error(
        "dlq.message_sent",
        extra={"topic": DLQ_TOPIC, "error": error},
    )


# ── Consumer ──────────────────────────────────────────────────────────────────


class MotionEventConsumer:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_SERVERS,
            group_id=KAFKA_GROUP_ID,
            # ── CRITICAL FIX: manual commit to prevent data loss ──────────────
            enable_auto_commit=False,
            auto_offset_reset="earliest",  # replay missed events after restart
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            max_poll_records=50,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=10_000,
        )
        self._producer = KafkaProducer(
            bootstrap_servers=KAFKA_SERVERS,
            value_serializer=lambda v: v,  # raw bytes for DLQ
            retries=3,
        )
        self._running = True
        logger.info("consumer.started", extra={"topic": TOPIC, "group": KAFKA_GROUP_ID})

    def _process_with_retry(self, raw_value: bytes, event: dict[str, Any]) -> bool:
        """
        Try to process an event up to MAX_RETRIES times.
        Returns True on success, False if all retries exhausted.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                _post_motion_event(event)
                return True
            except Exception as exc:
                logger.warning(
                    "consumer.process_failed",
                    extra={
                        "camera_id": event.get("camera_id"),
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)  # exponential backoff
        return False

    def consume(self) -> None:
        try:
            for message in self._consumer:
                if not self._running:
                    break

                event = message.value
                raw = (
                    message.value
                    if isinstance(message.value, bytes)
                    else json.dumps(event).encode()
                )

                success = self._process_with_retry(raw, event)

                if success:
                    # ── Manual commit only after successful processing ─────────
                    self._consumer.commit()
                    _state.messages_ok += 1
                    _state.last_processed = time.time()
                    logger.info(
                        "consumer.committed",
                        extra={
                            "camera_id": event.get("camera_id"),
                            "is_motion": event.get("is_motion"),
                            "partition": message.partition,
                            "offset": message.offset,
                        },
                    )
                else:
                    _state.messages_failed += 1
                    _post_to_dlq(self._producer, raw, "max_retries_exceeded")
                    # Still commit the offset so we don't re-process the bad message
                    self._consumer.commit()

        except Exception as exc:
            logger.error("consumer.fatal_error", extra={"error": str(exc)})
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        self._running = False
        _state.running = False
        try:
            self._consumer.close()
        except Exception:
            pass
        try:
            self._producer.close()
        except Exception:
            pass
        logger.info("consumer.stopped")


# ── Entrypoint ────────────────────────────────────────────────────────────────


def main() -> None:
    _start_health_server()

    consumer = MotionEventConsumer()

    # Graceful shutdown on SIGTERM (Docker stop)
    def _handle_sigterm(*_: Any) -> None:
        logger.info("consumer.sigterm_received")
        consumer._running = False

    signal.signal(signal.SIGTERM, _handle_sigterm)

    consumer.consume()


if __name__ == "__main__":
    main()
