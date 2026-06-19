"""
app/core/redis.py
Async Redis client using redis-py.
Single shared connection pool — do not create per-request clients.
"""

from redis.asyncio import Redis, from_url

from app.core.config import settings

redis_client: Redis = from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


async def close_redis() -> None:
    """Cleanly close the connection pool on app shutdown."""
    await redis_client.aclose()
