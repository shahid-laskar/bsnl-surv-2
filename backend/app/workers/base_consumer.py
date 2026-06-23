"""
workers/base_consumer.py — Phase 5 canonical base class.

Reconstructed from sarvanetra_implementation_plan.md §7.3, with three
gaps closed that the plan's pseudocode left open:

  1. Health HTTP server is now IN the base class (port configurable via
     HEALTH_PORT env var). Every concrete worker was hand-rolling an
     identical HealthHandler — that duplication is gone.
  2. SIGTERM handling is centralized here. Subclasses just implement
     `process()`; shutdown is handled once, correctly, in one place.
  3. `KafkaEvent.model_validate(message.value)` in the plan assumes every
     producer wraps payloads in the {event_id, event_type, timestamp,
     payload} envelope. Your onvif_producer.py does NOT do this — it
     publishes flat dicts like {"camera_id": ..., "is_motion": ...}.
     Rather than silently failing validation on every message, this base
     class accepts either shape: if the raw dict already looks like a
     KafkaEvent envelope, it's used as-is; otherwise it's wrapped in one
     automatically so `process()` always receives a consistent KafkaEvent.

Every concrete worker (motion_consumer, status_consumer, upload_worker)
extends BaseKafkaConsumer and implements only `process()`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import ConsumerRecord
from pydantic import BaseModel, Field

from app.core.config import settings  # noqa: F401  (settings.kafka_bootstrap_servers)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

MAX_RETRIES = 3
ENVELOPE_KEYS = {"event_id", "event_type", "timestamp", "payload"}


# ── Standard event envelope (plan §7.2) ────────────────────────────────────


class KafkaEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any]


def _coerce_to_event(raw: dict[str, Any], default_event_type: str) -> KafkaEvent:
    """
    Accept either a properly enveloped message or a flat payload dict
    (as currently emitted by onvif_producer.py) and normalize to KafkaEvent.
    """
    if ENVELOPE_KEYS.issubset(raw.keys()):
        return KafkaEvent.model_validate(raw)
    return KafkaEvent(event_type=default_event_type, payload=raw)


# ── Shared health state / HTTP server ──────────────────────────────────────


class _HealthState:
    def __init__(self) -> None:
        self.running = False
        self.started_at = time.time()
        self.messages_ok = 0
        self.messages_failed = 0
        self.messages_dlq = 0
        self.last_processed: float | None = None


class _HealthHandler(BaseHTTPRequestHandler):
    state: _HealthState  # set per-instance via factory below

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        s = self.state
        age = round(time.time() - s.last_processed, 1) if s.last_processed else None
        body = json.dumps(
            {
                "status": "ok" if s.running else "stopped",
                "uptime_seconds": round(time.time() - s.started_at, 1),
                "messages_ok": s.messages_ok,
                "messages_failed": s.messages_failed,
                "messages_dlq": s.messages_dlq,
                "last_processed_seconds_ago": age,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # suppress access log
        pass


def _make_health_handler(state: _HealthState) -> type[_HealthHandler]:
    return type("BoundHealthHandler", (_HealthHandler,), {"state": state})


# ── Base consumer ───────────────────────────────────────────────────────────


class BaseKafkaConsumer(ABC):
    """
    Abstract base for all Kafka consumers.
    Enforces: manual commit, DLQ, structured logging, health endpoint,
    graceful SIGTERM shutdown.

    Subclasses implement `process(event)` only. Everything else —
    retry/backoff, DLQ routing, offset commits, health checks, signal
    handling — lives here exactly once.
    """

    #: Override in subclass if the worker should label flat/unwrapped
    #: messages with something other than its topic name.
    default_event_type: str | None = None

    def __init__(self, topic: str, group_id: str, health_port: int) -> None:
        self.topic = topic
        self.group_id = group_id
        self.health_port = health_port
        self.logger = logging.getLogger(self.__class__.__name__)

        self._running = False
        self._consumer: AIOKafkaConsumer | None = None
        self._dlq_producer: AIOKafkaProducer | None = None
        self._health = _HealthState()
        self._health_server: HTTPServer | None = None

    @abstractmethod
    async def process(self, event: KafkaEvent) -> None:
        """Process a single event. Raise on failure — retry/DLQ handled by base."""
        ...

    # ── lifecycle ───────────────────────────────────────────────────────

    async def start(self) -> None:
        from app.core.config import settings  # local import keeps module importable in tests

        self._start_health_server()

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False,  # Manual commit ALWAYS
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        self._dlq_producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._consumer.start()
        await self._dlq_producer.start()
        self._running = True
        self._health.running = True

        self._install_sigterm_handler()

        self.logger.info(f"consumer.started topic={self.topic} group={self.group_id}")

        try:
            async for message in self._consumer:
                if not self._running:
                    break
                await self._handle_message(message)
        finally:
            await self._shutdown()

    def _install_sigterm_handler(self) -> None:
        loop = asyncio.get_event_loop()

        def _handle_sigterm(*_: Any) -> None:
            self.logger.info("consumer.sigterm_received")
            self._running = False

        try:
            loop.add_signal_handler(signal.SIGTERM, _handle_sigterm)
        except NotImplementedError:
            # Fallback for platforms without add_signal_handler (e.g. some test runners)
            signal.signal(signal.SIGTERM, _handle_sigterm)

    def _start_health_server(self) -> None:
        handler_cls = _make_health_handler(self._health)
        self._health_server = HTTPServer(("0.0.0.0", self.health_port), handler_cls)
        thread = threading.Thread(target=self._health_server.serve_forever, daemon=True)
        thread.start()
        self.logger.info(f"health_server.started port={self.health_port}")

    # ── message handling ────────────────────────────────────────────────

    async def _handle_message(self, message: ConsumerRecord) -> None:
        event_type = self.default_event_type or self.topic
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                event = _coerce_to_event(message.value, event_type)
                await self.process(event)
                await self._consumer.commit()  # Commit AFTER success
                self._health.messages_ok += 1
                self._health.last_processed = time.time()
                self.logger.info(
                    f"event.processed topic={self.topic} "
                    f"event_type={event.event_type} offset={message.offset}"
                )
                return
            except Exception as exc:
                self.logger.warning(
                    f"event.processing.failed attempt={attempt} "
                    f"error={exc} offset={message.offset}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    self._health.messages_failed += 1
                    await self._send_to_dlq(message, str(exc))
                    await self._consumer.commit()  # Commit to skip poison pill

    async def _send_to_dlq(self, message: ConsumerRecord, error: str) -> None:
        dlq_topic = f"{self.topic}.dlq"
        dlq_payload = {
            "original_topic": self.topic,
            "original_offset": message.offset,
            "original_value": message.value,
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._dlq_producer.send(dlq_topic, value=dlq_payload)
        self._health.messages_dlq += 1
        self.logger.error(f"event.sent_to_dlq topic={dlq_topic} error={error}")

    # ── shutdown ─────────────────────────────────────────────────────────

    async def _shutdown(self) -> None:
        self._running = False
        self._health.running = False
        if self._consumer is not None:
            await self._consumer.stop()
        if self._dlq_producer is not None:
            await self._dlq_producer.stop()
        if self._health_server is not None:
            self._health_server.shutdown()
        self.logger.info("consumer.stopped")
