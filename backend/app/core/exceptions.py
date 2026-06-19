"""
app/core/exceptions.py
Custom exception hierarchy for the Sarvanetra platform.

Every error raised in services and routers should be a subclass of
SarvanetraError so the global exception handler renders a consistent response:

    {
      "error": {
        "code": "CAMERA_NOT_FOUND",
        "message": "Camera 'CAMKLTVM00001' not found"
      }
    }

Never return raw {"error": "..."} dicts from endpoints.
"""

from typing import Any


class SarvanetraError(Exception):
    """Base class for all application exceptions."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str, **kwargs: Any) -> None:
        self.detail = detail
        self.extra = kwargs
        super().__init__(detail)


# ── 4xx Client Errors ─────────────────────────────────────────────────────────


class BadRequestError(SarvanetraError):
    status_code = 400
    error_code = "BAD_REQUEST"


class UnauthorizedError(SarvanetraError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(SarvanetraError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(SarvanetraError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(SarvanetraError):
    status_code = 409
    error_code = "CONFLICT"


class UnprocessableError(SarvanetraError):
    """Business rule violation (distinct from Pydantic validation errors)."""

    status_code = 422
    error_code = "UNPROCESSABLE"


# ── 5xx Server Errors ─────────────────────────────────────────────────────────


class ServiceUnavailableError(SarvanetraError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"


# ── Domain-specific errors ────────────────────────────────────────────────────


class CameraNotFoundError(NotFoundError):
    error_code = "CAMERA_NOT_FOUND"

    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Camera '{camera_id}' not found")


class CameraConflictError(ConflictError):
    error_code = "CAMERA_CONFLICT"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class CustomerNotFoundError(NotFoundError):
    error_code = "CUSTOMER_NOT_FOUND"

    def __init__(self, customer_id: int) -> None:
        super().__init__(f"Customer ID {customer_id} not found")


class DeviceNotFoundError(NotFoundError):
    error_code = "DEVICE_NOT_FOUND"

    def __init__(self, device_id: str | int) -> None:
        super().__init__(f"Device '{device_id}' not found")


class UserNotFoundError(NotFoundError):
    error_code = "USER_NOT_FOUND"

    def __init__(self, user_id: int | str) -> None:
        super().__init__(f"User '{user_id}' not found")


class MediaMTXError(ServiceUnavailableError):
    error_code = "MEDIAMTX_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"MediaMTX error: {detail}")


class MinIOError(ServiceUnavailableError):
    error_code = "MINIO_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"MinIO error: {detail}")


class CamIDGenerationError(UnprocessableError):
    error_code = "CAM_ID_GENERATION_FAILED"

    def __init__(self, detail: str) -> None:
        super().__init__(f"Camera ID generation failed: {detail}")
