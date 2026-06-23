"""
infra/minio_cleaner/clean.py

Scheduled retention-policy enforcement for the `recordings` bucket.
Deletes objects older than RETENTION_DAYS, checked once per CHECK_INTERVAL_SECONDS.

Object keys are expected in the shape produced by upload_worker.py:
    {cam_id}/{cam_id}_{YYYY-MM-DD_HH-MM-SS}.mp4
Age is determined from MinIO's own object.last_modified (the upload
timestamp), NOT by parsing the filename — this is correct regardless of
object naming and survives any future change to upload_worker's naming
scheme.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from minio import Minio
from minio.error import S3Error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s minio_cleaner %(levelname)s %(message)s",
)
logger = logging.getLogger("minio_cleaner")

MINIO_ENDPOINT = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
BUCKET = os.getenv("DEFAULT_BUCKET", "recordings")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CLEANER_INTERVAL_SECONDS", "3600"))

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)


def run_cleanup() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    deleted = 0
    scanned = 0
    errors = 0

    try:
        objects = client.list_objects(BUCKET, recursive=True)
        for obj in objects:
            scanned += 1
            if obj.last_modified is not None and obj.last_modified < cutoff:
                try:
                    client.remove_object(BUCKET, obj.object_name)
                    deleted += 1
                except S3Error as exc:
                    errors += 1
                    logger.error(f"delete.failed object={obj.object_name} error={exc}")
    except S3Error as exc:
        logger.error(f"cleanup.list_failed bucket={BUCKET} error={exc}")
        return

    logger.info(
        f"cleanup.complete bucket={BUCKET} scanned={scanned} "
        f"deleted={deleted} errors={errors} retention_days={RETENTION_DAYS}"
    )


def main() -> None:
    logger.info(
        f"cleaner.started bucket={BUCKET} retention_days={RETENTION_DAYS} "
        f"interval_s={CHECK_INTERVAL_SECONDS}"
    )
    while True:
        run_cleanup()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
