"""
app/core/logging.py
Structlog configuration for structured JSON logging.
No print() statements, no bare logging.info() calls anywhere in the codebase.

Usage:
    import structlog
    logger = structlog.get_logger(__name__)

    logger.info("camera.created", cam_id="CAMKLTVM00001", com_id=3)
    logger.error("mediamtx.unreachable", url=url, error=str(exc))
"""

import logging
import sys

import structlog


def configure_logging(debug: bool = False) -> None:
    """
    Configure structlog for JSON output in production, pretty output in debug.
    Call this once at application startup.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure stdlib logging to feed into structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy_logger).setLevel(logging.DEBUG if debug else logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        # Inject context vars set by middleware (e.g., request_id)
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.processors.add_log_level,
        # Add ISO timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Stack info for exceptions
        structlog.processors.StackInfoRenderer(),
    ]

    if debug:
        # Human-readable output for local development
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production log aggregation (Loki, ELK, etc.)
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
