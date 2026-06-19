"""
app/core/minio.py
MinIO client wrapper with presigned URL generation and retry logic.
"""

from datetime import timedelta
from functools import lru_cache

import structlog
from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import MinIOError

logger = structlog.get_logger(__name__)


@lru_cache
def get_minio_client() -> Minio:
    """Return a cached MinIO client instance."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create bucket if it does not exist."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("minio.bucket_created", bucket=bucket)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def upload_file(
    local_path: str,
    object_name: str,
    bucket: str | None = None,
    content_type: str = "video/mp4",
) -> str:
    """
    Upload a local file to MinIO with retry.
    Returns the object name on success.
    Raises MinIOError on permanent failure.
    """
    bucket = bucket or settings.minio_recordings_bucket
    client = get_minio_client()
    try:
        ensure_bucket(client, bucket)
        client.fput_object(bucket, object_name, local_path, content_type=content_type)
        logger.info("minio.upload_ok", bucket=bucket, object_name=object_name)
        return object_name
    except S3Error as exc:
        logger.error("minio.upload_failed", bucket=bucket, object=object_name, error=str(exc))
        raise MinIOError(str(exc)) from exc


def generate_presigned_url(
    object_name: str,
    bucket: str | None = None,
    expires_seconds: int = 3600,
) -> str:
    """
    Generate a presigned GET URL valid for `expires_seconds` seconds.
    Used to serve recordings to authenticated users.
    """
    bucket = bucket or settings.minio_recordings_bucket
    client = get_minio_client()
    try:
        url = client.presigned_get_object(
            bucket,
            object_name,
            expires=timedelta(seconds=expires_seconds),
        )
        return url
    except S3Error as exc:
        logger.error("minio.presign_failed", bucket=bucket, object=object_name, error=str(exc))
        raise MinIOError(str(exc)) from exc
