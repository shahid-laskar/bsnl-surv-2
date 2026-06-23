"""
app/services/minio_service.py
Service for interacting with MinIO object storage.
"""

import structlog
from minio.error import S3Error

from app.core.config import settings
from app.core.minio import ensure_bucket, generate_presigned_url, get_minio_client, upload_file

logger = structlog.get_logger(__name__)


class MinIOService:
    def __init__(self) -> None:
        self.client = get_minio_client()

    def generate_presigned_url(self, object_name: str, bucket: str | None = None, expires_seconds: int = 3600) -> str:
        """Generate a presigned GET URL for an object."""
        return generate_presigned_url(object_name, bucket, expires_seconds)

    def upload_file(self, local_path: str, object_name: str, bucket: str | None = None) -> str:
        """Upload a local file to MinIO."""
        return upload_file(local_path, object_name, bucket)

    def list_objects(self, prefix: str, bucket: str | None = None) -> list[str]:
        """List objects with a given prefix."""
        bucket_name = bucket or settings.minio_recordings_bucket
        ensure_bucket(self.client, bucket_name)
        
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error("minio.list_failed", error=str(e), prefix=prefix, bucket=bucket_name)
            return []

    def delete_object(self, object_name: str, bucket: str | None = None) -> None:
        """Delete an object from MinIO."""
        bucket_name = bucket or settings.minio_recordings_bucket
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info("minio.deleted", object_name=object_name, bucket=bucket_name)
        except S3Error as e:
            logger.error("minio.delete_failed", error=str(e), object_name=object_name, bucket=bucket_name)
