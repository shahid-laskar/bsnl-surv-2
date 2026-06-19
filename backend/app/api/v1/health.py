"""
app/api/v1/health.py
Liveness and readiness health check endpoints.

GET /health        — liveness: is the process alive?
GET /health/ready  — readiness: can the app serve traffic?
                     Checks DB connection and Redis ping.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """
    Returns 200 OK if the process is running.
    Kubernetes/Docker uses this for liveness probes.
    """
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    """
    Returns 200 OK only if DB and Redis are reachable.
    Returns 503 if any dependency is down.
    Kubernetes uses this to stop routing traffic during startup.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # Check PostgreSQL
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("health.db_check_failed", error=str(exc))
        checks["db"] = f"error: {exc}"
        all_ok = False

    # Check Redis
    try:
        from app.core.redis import redis_client  # imported lazily to avoid circular deps

        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("health.redis_check_failed", error=str(exc))
        checks["redis"] = f"error: {exc}"
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "degraded",
            **checks,
        },
    )
