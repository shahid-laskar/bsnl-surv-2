"""
app/core/middleware.py
ASGI middleware stack:
  1. RequestIDMiddleware  — injects X-Request-ID into every request/response
  2. AccessLogMiddleware  — structured JSON access log (replaces uvicorn default)
  3. register_exception_handlers — maps SarvanetraError → consistent JSON 4xx/5xx
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import SarvanetraError

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique request ID into every request and response.
    The ID is bound to structlog's context so it appears in every log line
    generated during that request.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Emit one structured log line per request with method, path, status, duration.
    Replaces uvicorn's plain-text access log.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Skip noisy health-check logs in production
        if request.url.path not in ("/health", "/health/ready"):
            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else None,
            )
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers so every unhandled error returns
    a consistent JSON shape:

        {"error": {"code": "CAMERA_NOT_FOUND", "message": "Camera 'X' not found"}}
    """

    @app.exception_handler(SarvanetraError)
    async def handle_app_error(request: Request, exc: SarvanetraError) -> JSONResponse:
        logger.warning(
            "http.app_error",
            error_code=exc.error_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.error_code, "message": exc.detail}},
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        logger.warning("http.validation_error", errors=exc.errors(), path=request.url.path)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "http.unhandled_error",
            exc_type=type(exc).__name__,
            detail=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
            },
        )
