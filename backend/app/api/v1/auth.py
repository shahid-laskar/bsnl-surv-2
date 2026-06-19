# app/api/v1/auth.py
import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, CurrentUser
from app.core.security import decode_stream_token
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserInResponse,
    ChangePasswordRequest,
    DeviceTokenRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.services.kong_service import KongService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db=db, kong=KongService())


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate with username + password.
    Returns access_token (JWT, 1h), refresh_token (opaque, 30d), and user info.
    """
    return await service.login(body)


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    body: TokenRefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenRefreshResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The submitted refresh token is revoked (single-use rotation).
    """
    return await service.refresh(body.refresh_token)


@router.get("/me", response_model=UserInResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Return the currently authenticated user's profile."""
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    """Change the current user's password."""
    await service.change_password(current_user.id, body.current_password, body.new_password)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: TokenRefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Revoke the refresh token.
    The access token continues to work until expiry (stateless JWT).
    Frontend must delete both tokens on logout.
    """
    await service.revoke_refresh_token(body.refresh_token)


@router.post("/device-token", status_code=status.HTTP_204_NO_CONTENT)
async def register_device_token(
    body: DeviceTokenRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    """Register an FCM/APNs push notification token for the current user."""
    await service.register_device_token(current_user.id, body.token, body.platform)


@router.post(
    "/validate-stream-token",
    response_model=MessageResponse,
    summary="Validate HLS stream token (Nginx auth_request target)",
)
async def validate_stream_token(
    token: str = Query(..., description="JWT stream token from HLS URL query param"),
) -> MessageResponse:
    """
    Validate a stream token issued by /cameras/{cam_id}/stream-token.
    Called internally by Nginx's auth_request directive before serving HLS segments.
    Returns 200 if valid, 401 if expired/invalid (via exception handler).
    """
    decode_stream_token(token)  # Raises UnauthorizedError on failure
    return MessageResponse(message="Token valid")
