"""
app/main.py
FastAPI application factory.

Startup order:
  1. Configure structlog
  2. Register middleware
  3. Mount routers
  4. Register exception handlers
  5. Lifespan: verify DB + Redis on startup; clean up on shutdown

Usage:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
  gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import v1_router
from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.logging import configure_logging
from app.core.middleware import (
    AccessLogMiddleware,
    RequestIDMiddleware,
    register_exception_handlers,
)
from app.core.redis import close_redis, redis_client
from app.services.kafka_service import KafkaProducerService

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup / shutdown lifecycle.
    Fails fast if the database or Redis is unreachable at startup.
    """
    logger.info("app.startup", version=settings.app_version, debug=settings.debug)

    # Verify database connectivity
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("app.db_ok")
    except Exception as exc:
        logger.error("app.db_unreachable", error=str(exc))
        raise

    # Verify Redis connectivity
    try:
        await redis_client.ping()
        logger.info("app.redis_ok")
    except Exception as exc:
        logger.error("app.redis_unreachable", error=str(exc))
        raise

    producer = KafkaProducerService()
    await producer.start()

    yield  # ── Application is running ──

    # Shutdown: close connection pools
    logger.info("app.shutdown")
    await producer.stop()
    await engine.dispose()
    await close_redis()
    logger.info("app.shutdown_complete")


def create_app() -> FastAPI:
    """Application factory."""
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware (order matters — outermost first) ───────────────────
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    from app.api.v1.internal import router as internal_router
    app.include_router(internal_router)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    return app


app = create_app()
