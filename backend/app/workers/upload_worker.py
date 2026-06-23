"""
workers/upload_worker/main.py — Phase 5, rewritten against BaseKafkaConsumer.

Domain logic only: parse the recording-segment path, hash the file,
upload to MinIO, register the segment with FastAPI. Retry/DLQ/manual
commit/health/SIGTERM all come from BaseKafkaConsumer.

Two blocking operations from the original file are moved off the event
loop with asyncio.to_thread instead of running them inline, since the
original synchronous version would otherwise stall the consumer's main
loop for every segment:
  - SHA-256 hashing (reads the whole file in chunks)
  - MinIO fput_object (the minio SDK is sync-only)

MinIO upload retry (tenacity, exponential backoff) is preserved as-is —
this is upload-specific retry (network blip mid-PUT), which is a
different concern from the base class's per-message retry (which would
otherwise re-hash and re-upload the whole file on every attempt).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from minio import Minio
from tenacity import retry, stop_after_attempt, wait_exponential

from workers.base_consumer import BaseKafkaConsumer, KafkaEvent

TOPIC = os.getenv("KAFKA_TOPIC_RECORDINGS", "recording.segments")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "upload-workers")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8083"))

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("DEFAULT_BUCKET", "recordings")

FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://sarvanetra_api:8000")
HTTP_TIMEOUT = httpx.Timeout(10.0)

_minio = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)


def _sha256_sync(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _upload_sync(local_path: str, object_name: str) -> None:
    if not _minio.bucket_exists(MINIO_BUCKET):
        _minio.make_bucket(MINIO_BUCKET)
    _minio.fput_object(MINIO_BUCKET, object_name, local_path, content_type="video/mp4")


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


class UploadWorker(BaseKafkaConsumer):
    default_event_type = "recording.segments"

    def __init__(self) -> None:
        super().__init__(topic=TOPIC, group_id=GROUP_ID, health_port=HEALTH_PORT)
        self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

    async def process(self, event: KafkaEvent) -> None:
        payload: dict[str, Any] = event.payload
        file_path = payload.get("file_path", "")
        duration_str = payload.get("segment_duration", "0")

        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        cam_id, start_time = _parse_recording_path(file_path)
        duration = float(str(duration_str).rstrip("s")) if duration_str else 0.0
        end_time = start_time.replace(second=start_time.second + int(duration))
        file_size = os.path.getsize(file_path)

        # Blocking I/O off the event loop — does NOT stall other workers' polling.
        sha256 = await asyncio.to_thread(_sha256_sync, file_path)

        ts_str = start_time.strftime("%Y-%m-%d_%H-%M-%S")
        object_name = f"{cam_id}/{cam_id}_{ts_str}.mp4"

        await asyncio.to_thread(_upload_sync, file_path, object_name)
        self.logger.info(f"upload.ok cam_id={cam_id} object={object_name} bytes={file_size}")

        resp = await self._client.post(
            f"{FASTAPI_URL}/api/v1/recordings/segments",
            json={
                "cam_id": cam_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration": duration,
                "file_path": object_name,
                "file_size": file_size,
                "minio_bucket": MINIO_BUCKET,
                "sha256": sha256,
            },
        )
        resp.raise_for_status()
        self.logger.info(f"segment.registered cam_id={cam_id} sha256={sha256[:12]}")

    async def _shutdown(self) -> None:
        await self._client.aclose()
        await super()._shutdown()


async def main() -> None:
    worker = UploadWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())