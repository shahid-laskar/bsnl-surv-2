"""
workers/upload_worker.py — Phase 5 reliability fix.

Key changes from original:
  1. enable_auto_commit=False   → manual commit after successful upload + DB write
  2. SHA-256 hash computed before upload, stored with segment record
  3. MinIO upload retried 3x with exponential backoff (tenacity)
  4. Dead Letter Queue for messages that fail all retries
  5. Health HTTP endpoint on port 8083
  6. Posts segment to FastAPI /api/v1/recordings/segments (not direct DB)
  7. Graceful SIGTERM shutdown
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import requests
from kafka import KafkaConsumer, KafkaProducer
from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("upload_worker")

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "upload-workers")
TOPIC = os.getenv("KAFKA_TOPIC_RECORDINGS", "recording.segments")
DLQ_TOPIC = f"{TOPIC}.dlq"
MAX_RETRIES = 3

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("DEFAULT_BUCKET", "recordings")

FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")
RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", "/recordings")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8083"))

# ── Metrics ───────────────────────────────────────────────────────────────────


class _State:
    ok: int = 0
    failed: int = 0
    dlq: int = 0
    last_ok: float = time.time()
    running: bool = True


_s = _State()


# ── Health server ─────────────────────────────────────────────────────────────


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(
            {
                "status": "ok" if _s.running else "stopped",
                "uploaded_ok": _s.ok,
                "upload_failed": _s.failed,
                "dlq_sent": _s.dlq,
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


# ── MinIO upload with retry ───────────────────────────────────────────────────

_minio = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _upload(local_path: str, object_name: str) -> None:
    if not _minio.bucket_exists(MINIO_BUCKET):
        _minio.make_bucket(MINIO_BUCKET)
    _minio.fput_object(MINIO_BUCKET, object_name, local_path, content_type="video/mp4")


# ── Segment registration with FastAPI ────────────────────────────────────────


def _register_segment(
    cam_id: str,
    start_time: str,
    end_time: str,
    duration: float,
    object_name: str,
    file_size: int,
    sha256: str,
) -> None:
    """POST segment info to FastAPI — FastAPI writes to DB."""
    payload = {
        "cam_id": cam_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "file_path": object_name,
        "file_size": file_size,
        "minio_bucket": MINIO_BUCKET,
        "sha256": sha256,
    }
    resp = requests.post(
        f"{FASTAPI_URL}/api/v1/recordings/segments",
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


# ── Message processor ─────────────────────────────────────────────────────────


def _parse_recording_path(file_path: str) -> tuple[str, datetime]:
    """
    Parse /recordings/CAMKLTVM00001/2025/06/18/11-01-26-983631-live/CAMKLTVM00001.mp4
    Returns (cam_id, start_time).
    """
    parts = file_path.strip("/").split("/")
    try:
        rec_idx = parts.index("recordings")
    except ValueError:
        rec_idx = -1

    # Find year
    year_idx = None
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4 and 2000 <= int(p) <= 2100:
            year_idx = i
            break

    if year_idx is None:
        raise ValueError(f"No year found in path: {file_path}")

    cam_id = "/".join(parts[rec_idx + 1 : year_idx])
    year, month, day = parts[year_idx], parts[year_idx + 1], parts[year_idx + 2]
    ts_dir = parts[year_idx + 3].removesuffix("-live").removesuffix(f"-{cam_id}")
    hh, mm, ss, *micro_parts = ts_dir.split("-")
    micro = int(micro_parts[0]) // 1000 if micro_parts else 0

    dt = datetime(
        int(year), int(month), int(day), int(hh), int(mm), int(ss), micro, tzinfo=timezone.utc
    )
    return cam_id, dt


def process_message(event: dict[str, Any]) -> None:
    camera_path = event.get("camera_path", "")
    file_path = event.get("file_path", "")
    duration_str = event.get("segment_duration", "0")

    if not file_path or not Path(file_path).exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    cam_id, start_time = _parse_recording_path(file_path)
    duration = float(str(duration_str).rstrip("s")) if duration_str else 0.0
    end_time = start_time.replace(second=start_time.second + int(duration))
    file_size = os.path.getsize(file_path)

    # Compute SHA-256 before upload
    sha256 = _sha256(file_path)

    # Build object name
    ts_str = start_time.strftime("%Y-%m-%d_%H-%M-%S")
    object_name = f"{cam_id}/{cam_id}_{ts_str}.mp4"

    # Upload with retry
    _upload(file_path, object_name)
    logger.info(
        "upload.ok",
        extra={"cam_id": cam_id, "object": object_name, "bytes": file_size},
    )

    # Register with FastAPI
    _register_segment(
        cam_id=cam_id,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration=duration,
        object_name=object_name,
        file_size=file_size,
        sha256=sha256,
    )
    logger.info("segment.registered", extra={"cam_id": cam_id, "sha256": sha256[:12]})


# ── Upload Worker ─────────────────────────────────────────────────────────────


class UploadWorker:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_SERVERS,
            group_id=KAFKA_GROUP_ID,
            enable_auto_commit=False,  # manual commit
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            max_poll_records=50,
            session_timeout_ms=60_000,
        )
        self._dlq = KafkaProducer(
            bootstrap_servers=KAFKA_SERVERS,
            value_serializer=lambda v: v,
            retries=3,
        )
        self._running = True
        logger.info("worker.started", extra={"topic": TOPIC, "group": KAFKA_GROUP_ID})

    def run(self) -> None:
        try:
            for message in self._consumer:
                if not self._running:
                    break

                event = message.value
                success = False

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        process_message(event)
                        success = True
                        break
                    except Exception as exc:
                        logger.warning(
                            "worker.attempt_failed",
                            extra={"attempt": attempt, "error": str(exc)},
                        )
                        if attempt < MAX_RETRIES:
                            time.sleep(2**attempt)

                if success:
                    self._consumer.commit()
                    _s.ok += 1
                    _s.last_ok = time.time()
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
                    _s.dlq += 1
                    # Commit bad message so we don't loop on it forever
                    self._consumer.commit()
                    logger.error("worker.dlq_sent", extra={"topic": DLQ_TOPIC})

        except Exception as exc:
            logger.error("worker.fatal", extra={"error": str(exc)})
        finally:
            self._consumer.close()
            self._dlq.close()
            _s.running = False
            logger.info("worker.stopped")

    def stop(self) -> None:
        self._running = False


def main() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    worker = UploadWorker()

    def _sigterm(*_: Any) -> None:
        logger.info("worker.sigterm")
        worker.stop()

    signal.signal(signal.SIGTERM, _sigterm)
    worker.run()


if __name__ == "__main__":
    main()
