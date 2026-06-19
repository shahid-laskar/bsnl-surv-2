# app/services/kong_service.py
# Manages Kong consumer lifecycle for each Sarvanetra user.

import httpx
import structlog
from app.core.config import settings
from app.core.exceptions import SarvanetraError

logger = structlog.get_logger(__name__)


class KongError(SarvanetraError):
    status_code = 502
    error_code = "KONG_ERROR"


class KongService:
    def __init__(self) -> None:
        self._base_url = settings.kong_admin_url  # e.g. http://kong:8001
        # No auth on Kong Admin API (internal network only)

    async def create_consumer_and_credential(self, user_id: int) -> tuple[str, str]:
        """
        Create a Kong consumer and JWT credential for a new user.
        Returns (kong_consumer_username, jwt_key).
        Idempotent — safe to call multiple times for the same user_id.
        """
        consumer_username = f"user_{user_id}"
        jwt_key = f"sarvanetra_user_{user_id}"

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            # Create consumer (ignore 409 conflict — already exists)
            resp = await client.post("/consumers", json={"username": consumer_username})
            if resp.status_code not in (200, 201, 409):
                raise KongError(f"Failed to create Kong consumer: {resp.text}")

            # Create JWT credential
            resp = await client.post(
                f"/consumers/{consumer_username}/jwt",
                data={
                    "key": jwt_key,
                    "secret": settings.jwt_secret_key,
                    "algorithm": "HS256",
                },
            )
            if resp.status_code not in (200, 201, 409):
                raise KongError(f"Failed to create JWT credential: {resp.text}")

        logger.info("kong.consumer.created", user_id=user_id, jwt_key=jwt_key)
        return consumer_username, jwt_key

    async def delete_consumer(self, kong_consumer_username: str) -> None:
        """
        Delete a Kong consumer and all its credentials.
        All JWTs issued for this consumer are immediately invalidated.
        """
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.delete(f"/consumers/{kong_consumer_username}")
            if resp.status_code not in (204, 404):
                raise KongError(f"Failed to delete Kong consumer: {resp.text}")

        logger.info("kong.consumer.deleted", username=kong_consumer_username)

    async def health_check(self) -> bool:
        """Return True if Kong Admin API is reachable."""
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=5.0) as client:
                resp = await client.get("/")
                return resp.status_code == 200
        except Exception:
            return False
