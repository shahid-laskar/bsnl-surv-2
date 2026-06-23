# app/services/auth_service.py

from datetime import datetime, timedelta, UTC
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ConflictError, NotFoundError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.models.auth import SvUser, SvKongConsumer, SvRefreshToken
from app.schemas.auth import LoginRequest, LoginResponse, TokenRefreshResponse
from app.services.kong_service import KongService

logger = structlog.get_logger(__name__)

REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    def __init__(self, db: AsyncSession, kong: KongService) -> None:
        self._db = db
        self._kong = kong

    async def login(self, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and return access + refresh tokens.
        Raises UnauthorizedError on bad credentials or inactive user.
        """
        user = await self._get_user_by_username(request.username)
        if not user:
            # Constant-time compare to prevent user enumeration
            verify_password("dummy", "$2b$12$dummy.hash.to.prevent.timing.attack.xxx")
            raise UnauthorizedError("Invalid username or password")

        if not verify_password(request.password, user.password_hash):
            raise UnauthorizedError("Invalid username or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        # Get Kong consumer to build the correct iss claim
        kong_consumer = await self._get_kong_consumer(user.id)
        if not kong_consumer:
            if user.is_superuser or user.role == "sysadmin":
                # Auto-provision Kong consumer for seeded admin
                consumer_username, jwt_key = await self._kong.create_consumer_and_credential(user.id)
                kong_consumer = SvKongConsumer(
                    user_id=user.id,
                    kong_consumer_username=consumer_username,
                    jwt_key=jwt_key,
                    is_active=True,
                )
                self._db.add(kong_consumer)
            else:
                raise UnauthorizedError("User has no Kong credential — contact admin")

        # Build access token
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            com_id=user.com_id,
            cir_id=user.cir_id,
            ba_id=user.ba_id,
            jwt_key=kong_consumer.jwt_key,
        )

        # Build refresh token
        raw_refresh, refresh_hash = create_refresh_token()

        # Insert refresh token
        new_token_record = SvRefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            device_id=request.device_id,
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self._db.add(new_token_record)

        # Update last login
        user.last_login = datetime.now(UTC)

        await self._db.commit()

        logger.info("auth.login.success", user_id=user.id, role=user.role)

        from app.schemas.auth import UserInResponse

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=3600,
            user=UserInResponse.model_validate(user),
        )

    async def refresh(self, raw_refresh_token: str) -> TokenRefreshResponse:
        """Rotate refresh token and issue new access token."""
        token_hash = hash_refresh_token(raw_refresh_token)

        result = await self._db.execute(
            select(SvRefreshToken)
            .where(SvRefreshToken.token_hash == token_hash)
            .where(SvRefreshToken.revoked == False)  # noqa: E712
            .where(SvRefreshToken.expires_at > datetime.now(UTC))
        )
        refresh_record = result.scalar_one_or_none()

        if not refresh_record:
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await self._get_user_by_id(refresh_record.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        kong_consumer = await self._get_kong_consumer(user.id)
        if not kong_consumer:
            raise UnauthorizedError("User has no Kong credential")

        # Revoke old token (rotation — one use only)
        refresh_record.revoked = True
        refresh_record.revoked_at = datetime.now(UTC)

        # New access token
        new_access = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            com_id=user.com_id,
            cir_id=user.cir_id,
            ba_id=user.ba_id,
            jwt_key=kong_consumer.jwt_key,
        )

        # New refresh token
        new_raw, new_hash = create_refresh_token()
        new_token_record = SvRefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            device_id=refresh_record.device_id,
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self._db.add(new_token_record)
        await self._db.commit()

        return TokenRefreshResponse(
            access_token=new_access,
            refresh_token=new_raw,
            token_type="bearer",
            expires_in=3600,
        )

    async def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        """Change the password for a user after verifying the current password."""
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Invalid current password")

        user.password_hash = hash_password(new_password)
        await self._db.commit()
        logger.info("auth.change_password.success", user_id=user_id)

    async def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        """Revoke a refresh token by its raw value."""
        token_hash = hash_refresh_token(raw_refresh_token)
        result = await self._db.execute(
            select(SvRefreshToken).where(SvRefreshToken.token_hash == token_hash)
        )
        refresh_record = result.scalar_one_or_none()
        if refresh_record:
            refresh_record.revoked = True
            refresh_record.revoked_at = datetime.now(UTC)
            await self._db.commit()
            logger.info("auth.revoke_token.success", user_id=refresh_record.user_id)
        else:
            logger.warning("auth.revoke_token.not_found")

    async def register_device_token(self, user_id: int, token: str, platform: str) -> None:
        """Register a new device token for push notifications."""
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        device_tokens = list(user.device_tokens or [])
        exists = any(
            entry.get("token") == token for entry in device_tokens if isinstance(entry, dict)
        )
        if not exists:
            device_tokens.append(
                {
                    "token": token,
                    "platform": platform,
                    "registered_at": datetime.now(UTC).isoformat(),
                }
            )
            user.device_tokens = device_tokens
            await self._db.commit()
            logger.info("auth.register_device_token.success", user_id=user_id, platform=platform)

    async def _get_user_by_username(self, username: str) -> SvUser | None:
        result = await self._db.execute(select(SvUser).where(SvUser.username == username))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: int) -> SvUser | None:
        result = await self._db.execute(select(SvUser).where(SvUser.id == user_id))
        return result.scalar_one_or_none()

    async def _get_kong_consumer(self, user_id: int) -> SvKongConsumer | None:
        result = await self._db.execute(
            select(SvKongConsumer)
            .where(SvKongConsumer.user_id == user_id)
            .where(SvKongConsumer.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()
