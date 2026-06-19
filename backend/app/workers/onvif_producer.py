"""
onvif_motion_producer_async.py — Phase 5 reliability fix.

Replaces the ThreadPoolExecutor approach with asyncio.
Each camera is an asyncio Task (coroutine), not a thread.
asyncio can handle 100+ concurrent ONVIF subscriptions with a single OS thread.

Key changes from the original:
  1. asyncio replaces ThreadPoolExecutor
  2. aiohttp replaces blocking requests
  3. Structured logging replaces bare print/logger calls
  4. Health HTTP endpoint on port 8082
  5. Semaphore limits concurrent ONVIF calls to prevent overwhelming cameras
  6. Reconnect delay uses exponential backoff with a 5-minute ceiling
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import aiohttp
from aiokafka import AIOKafkaProducer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("onvif_producer")

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MAX_CAMERAS = int(os.getenv("MAX_CAMERAS_PER_WORKER", "25"))
DISCOVERY_INTERVAL = int(os.getenv("CAMERA_DISCOVERY_INTERVAL", "60"))
WORKER_ID = os.getenv("HOSTNAME", "worker-1")
DB_URL = os.getenv("DATABASE_URL", "")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8082"))
# Max concurrent ONVIF subscription creations at once
ONVIF_CONCURRENCY = int(os.getenv("ONVIF_CONCURRENCY", "10"))

TOPIC_MOTION = "camera.motion"
TOPIC_STATUS = "camera.status"


# ── Metrics ───────────────────────────────────────────────────────────────────


@dataclass
class WorkerMetrics:
    cameras_monitored: int = 0
    events_published: int = 0
    subscription_errors: int = 0
    last_event_time: float = field(default_factory=time.time)


_metrics = WorkerMetrics()


# ── Health server ─────────────────────────────────────────────────────────────


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(
            {
                "worker_id": WORKER_ID,
                "cameras_monitored": _metrics.cameras_monitored,
                "events_published": _metrics.events_published,
                "subscription_errors": _metrics.subscription_errors,
                "last_event_seconds_ago": round(time.time() - _metrics.last_event_time, 1),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


# ── Camera discovery (PostgreSQL via asyncpg) ─────────────────────────────────


async def fetch_assigned_cameras() -> list[dict[str, Any]]:
    """
    Query camera_master for active, motion-enabled cameras assigned to this worker.
    Uses asyncpg directly — no Django ORM needed.
    """
    try:
        import asyncpg

        conn = await asyncpg.connect(DB_URL)
        try:
            worker_num = int(WORKER_ID.split("-")[-1]) if "-" in WORKER_ID else 1
            offset = (worker_num - 1) * MAX_CAMERAS

            rows = await conn.fetch(
                """
                SELECT cam_id, cam_usrname, cam_pass, cam_strm1, cam_onvif
                FROM sv_camera_master
                WHERE is_active = TRUE AND motion_active = TRUE
                ORDER BY cam_id
                LIMIT $1 OFFSET $2
                """,
                MAX_CAMERAS,
                offset,
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("discovery.db_error", extra={"error": str(exc)})
        return []


# ── ONVIF subscription (async) ────────────────────────────────────────────────


def _extract_ip(stream_url: str) -> str | None:
    """Extract IP from rtsp://user:pass@ip:port/path."""
    try:
        url = stream_url
        if "://" in url:
            url = url.split("://", 1)[1]
        if "@" in url:
            url = url.split("@", 1)[1]
        return url.split(":")[0].split("/")[0]
    except Exception:
        return None


async def create_onvif_subscription(
    session: aiohttp.ClientSession,
    cam: dict[str, Any],
) -> str | None:
    """
    Create a PullPoint subscription via ONVIF SOAP.
    Returns the subscription address or None on failure.
    """
    ip = _extract_ip(cam["cam_strm1"] or "")
    port = cam["cam_onvif"] or 80
    cam_id = cam["cam_id"]

    if not ip:
        logger.warning("onvif.no_ip", extra={"cam_id": cam_id})
        return None

    endpoint = f"http://{ip}:{port}/onvif/events"
    soap = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tev="http://www.onvif.org/ver10/events/wsdl">
  <s:Body>
    <tev:CreatePullPointSubscription>
      <tev:InitialTerminationTime>PT60M</tev:InitialTerminationTime>
    </tev:CreatePullPointSubscription>
  </s:Body>
</s:Envelope>"""

    try:
        async with session.post(
            endpoint,
            data=soap,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            auth=aiohttp.BasicAuth(cam["cam_usrname"] or "", cam["cam_pass"] or ""),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            text = await resp.text()
            # Parse subscription address from SOAP response
            import xml.etree.ElementTree as ET

            root = ET.fromstring(text)
            addr_elem = root.find(".//{http://www.w3.org/2005/08/addressing}Address")
            if addr_elem is not None and addr_elem.text:
                logger.info(
                    "onvif.subscribed", extra={"cam_id": cam_id, "address": addr_elem.text[:60]}
                )
                return addr_elem.text
            logger.warning(
                "onvif.no_address_in_response", extra={"cam_id": cam_id, "body": text[:200]}
            )
            return None
    except Exception as exc:
        logger.error("onvif.subscribe_failed", extra={"cam_id": cam_id, "error": str(exc)})
        _metrics.subscription_errors += 1
        return None


async def pull_events(
    session: aiohttp.ClientSession,
    subscription_addr: str,
    cam: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pull pending ONVIF events from the subscription endpoint."""
    soap = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tev="http://www.onvif.org/ver10/events/wsdl">
  <s:Body>
    <tev:PullMessages>
      <tev:Timeout>PT5S</tev:Timeout>
      <tev:MessageLimit>10</tev:MessageLimit>
    </tev:PullMessages>
  </s:Body>
</s:Envelope>"""

    try:
        async with session.post(
            subscription_addr,
            data=soap,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            text = await resp.text()

        import xml.etree.ElementTree as ET

        root = ET.fromstring(text)
        ns = {
            "wsnt": "http://docs.oasis-open.org/wsn/b-2",
            "tt": "http://www.onvif.org/ver10/schema",
        }
        events = []
        for msg in root.findall(".//wsnt:NotificationMessage", ns):
            msg_elem = msg.find(".//tt:Message", ns)
            if msg_elem is None:
                continue
            data_items = {
                item.get("Name"): item.get("Value")
                for item in msg_elem.findall(".//tt:Data/tt:SimpleItem", ns)
            }
            is_motion = data_items.get("IsMotion", "false").lower() == "true"
            utc_time = msg_elem.get("UtcTime", datetime.now(timezone.utc).isoformat() + "Z")
            events.append(
                {
                    "camera_id": cam["cam_id"],
                    "is_motion": is_motion,
                    "timestamp": utc_time,
                    "source": "onvif",
                    "data": data_items,
                }
            )
        return events
    except Exception as exc:
        raise RuntimeError(f"pull_events failed: {exc}") from exc


# ── Per-camera monitor coroutine ──────────────────────────────────────────────


async def monitor_camera(
    cam: dict[str, Any],
    producer: AIOKafkaProducer,
    semaphore: asyncio.Semaphore,
    stop_event: asyncio.Event,
) -> None:
    """
    Continuously monitor one camera: subscribe → pull → publish → repeat.
    Uses exponential backoff on errors with a 5-minute ceiling.
    """
    cam_id = cam["cam_id"]
    backoff = 5  # seconds
    subscription_addr: str | None = None

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            # Subscribe if needed
            if subscription_addr is None:
                async with semaphore:  # limit concurrent subscription creations
                    subscription_addr = await create_onvif_subscription(session, cam)

                if subscription_addr is None:
                    logger.warning(
                        "monitor.retrying",
                        extra={"cam_id": cam_id, "backoff_s": backoff},
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)  # cap at 5 minutes
                    continue

                backoff = 5  # reset on success

            # Pull events
            try:
                events = await pull_events(session, subscription_addr, cam)
                for event in events:
                    await producer.send_and_wait(
                        TOPIC_MOTION,
                        value=json.dumps(event).encode("utf-8"),
                    )
                    _metrics.events_published += 1
                    _metrics.last_event_time = time.time()
                    logger.info(
                        "event.published",
                        extra={
                            "cam_id": cam_id,
                            "is_motion": event["is_motion"],
                        },
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                error_str = str(exc)
                logger.warning(
                    "monitor.pull_error",
                    extra={"cam_id": cam_id, "error": error_str},
                )
                # Reset subscription if the endpoint is dead
                dead_signals = (
                    "Connection refused",
                    "timed out",
                    "NewConnectionError",
                    "No such subscription",
                )
                if any(s in error_str for s in dead_signals):
                    subscription_addr = None
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)

    logger.info("monitor.stopped", extra={"cam_id": cam_id})


# ── Main worker ───────────────────────────────────────────────────────────────


async def run_worker() -> None:
    stop_event = asyncio.Event()
    semaphore = asyncio.Semaphore(ONVIF_CONCURRENCY)

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        compression_type="gzip",
        linger_ms=100,
    )
    await producer.start()

    active_tasks: dict[str, asyncio.Task] = {}  # cam_id → Task

    try:
        while not stop_event.is_set():
            cameras = await fetch_assigned_cameras()
            current_ids = {c["cam_id"] for c in cameras}

            # Start monitoring new cameras
            for cam in cameras:
                cid = cam["cam_id"]
                if cid not in active_tasks or active_tasks[cid].done():
                    task = asyncio.create_task(
                        monitor_camera(cam, producer, semaphore, stop_event),
                        name=f"monitor-{cid}",
                    )
                    active_tasks[cid] = task
                    logger.info("worker.camera_added", extra={"cam_id": cid})

            # Cancel tasks for removed cameras
            for cid in list(active_tasks.keys()):
                if cid not in current_ids:
                    active_tasks[cid].cancel()
                    del active_tasks[cid]
                    logger.info("worker.camera_removed", extra={"cam_id": cid})

            _metrics.cameras_monitored = len(active_tasks)
            logger.info(
                "worker.discovery_done",
                extra={"monitoring": _metrics.cameras_monitored},
            )
            await asyncio.sleep(DISCOVERY_INTERVAL)

    except asyncio.CancelledError:
        pass
    finally:
        stop_event.set()
        for task in active_tasks.values():
            task.cancel()
        await asyncio.gather(*active_tasks.values(), return_exceptions=True)
        await producer.stop()
        logger.info("worker.shutdown_complete")


def main() -> None:
    # Start health server in background thread
    import threading

    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    loop = asyncio.new_event_loop()

    def _handle_sigterm(*_: Any) -> None:
        logger.info("worker.sigterm")
        loop.call_soon_threadsafe(loop.stop)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        loop.run_until_complete(run_worker())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
