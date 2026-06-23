"""
app/core/dependencies.py
FastAPI dependency injection for auth, DB, and services.
Import these in routers — never import services or DB directly in routers.
"""

from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.auth import SvUser

logger = structlog.get_logger(__name__)

# OAuth2 bearer scheme for native auth flow
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> SvUser:
    """
    Validate the Bearer JWT token and return the authenticated SvUser.
    Raises UnauthorizedError if token is missing, invalid, or expired.
    Raises UnauthorizedError if user is not found or inactive.
    """
    if not token:
        raise UnauthorizedError("Authentication required")

    payload = decode_access_token(token)

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise UnauthorizedError("Token missing user_id claim")

    result = await db.execute(select(SvUser).where(SvUser.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("auth.user_not_found", user_id=user_id)
        raise UnauthorizedError("User not found")

    if not user.is_active:
        logger.warning("auth.user_inactive", user_id=user_id)
        raise UnauthorizedError("Account is deactivated")

    return user


# Type alias for injecting current user
CurrentUser = SvUser


def require_role(*roles: str):
    """
    Role-based access control dependency factory.

    Usage:
        @router.delete("/{cam_id}")
        async def delete_camera(
            _: SvUser = Depends(require_role("sysadmin", "circle_admin")),
        ):
            ...
    """

    async def _check_role(
        current_user: SvUser = Depends(get_current_user),
    ) -> SvUser:
        if current_user.is_superuser:
            return current_user
        if current_user.role not in roles:
            logger.warning(
                "auth.role_denied",
                user_id=current_user.id,
                user_role=current_user.role,
                required_roles=roles,
            )
            raise ForbiddenError(
                f"Role '{current_user.role}' is not permitted. " f"Required: {', '.join(roles)}"
            )
        return current_user

    return _check_role


def require_any_role(*roles: str):
    """Alias of require_role — more readable at call sites."""
    return require_role(*roles)


def get_scoped_com_id(current_user: SvUser = Depends(get_current_user)) -> int | None:
    """
    Returns the com_id that should be used for filtering queries.
    - sysadmin returns None (no filter — sees all)
    - circle_admin returns None (filtered by cir_id instead)
    - ba_admin returns None (filtered by ba_id instead)
    - cust_admin / viewer returns their com_id
    """
    if current_user.role in ("sysadmin", "circle_admin", "ba_admin"):
        return None
    return current_user.com_id


def assert_company_access(user: SvUser, com_id: int) -> None:
    """
    Raise ForbiddenError if `user` cannot access a resource scoped to `com_id`.

    sysadmin / circle_admin / ba_admin pass through here — any further
    narrowing (e.g. "only this circle's customers") happens at the query
    level in the relevant service, same pattern as cameras.py's
    `_assert_customer_access`. cust_admin / viewer are hard-restricted to
    their own company.
    """
    if user.role in ("sysadmin", "circle_admin", "ba_admin"):
        return
    if user.com_id != com_id:
        raise ForbiddenError(f"Access to company {com_id} is not permitted for your account")