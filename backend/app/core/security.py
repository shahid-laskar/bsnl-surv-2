"""
app/core/security.py
JWT creation and validation.

Token design:
  - The `iss` claim must equal settings.jwt_key ("cctv@Bsnl" by default)
    to match the existing Kong JWT consumer credential.
  - Stream tokens are shorter-lived (15 min) and include cam_id.
  - Access tokens are longer-lived (60 min) and include user role/scope.

Both token types are validated by this module.
Kong validates only the iss + signature; FastAPI validates the full payload.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
import bcrypt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# ── Password utilities ────────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    pw_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ── JWT utilities ─────────────────────────────────────────────────────────────


def _build_base_payload(
    expire_minutes: int, extra: dict[str, Any], jwt_key: str | None = None
) -> dict[str, Any]:
    """Build the standard JWT payload with timing claims."""
    now = datetime.now(UTC)
    return {
        "iss": jwt_key or settings.jwt_key,  # Kong consumer key — must match exactly
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        **extra,
    }


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    cir_id: int | None = None,
    ba_id: int | None = None,
    com_id: int | None = None,
    jwt_key: str | None = None,
) -> str:
    """
    Generate a long-lived JWT for API access.
    Embeds role and scope so every endpoint can check permissions
    without an extra DB query per request.
    """
    payload = _build_base_payload(
        expire_minutes=settings.jwt_access_token_expire_minutes,
        jwt_key=jwt_key,
        extra={
            "type": "access",
            "user_id": user_id,
            "username": username,
            "role": role,
            "cir_id": cir_id,
            "ba_id": ba_id,
            "com_id": com_id,
        },
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_stream_token(cam_id: str, user_id: int) -> str:
    """
    Generate a short-lived JWT for HLS stream access.
    Nginx auth_request calls /validate-stream-token with this token.
    """
    payload = _build_base_payload(
        expire_minutes=settings.jwt_stream_token_expire_minutes,
        extra={
            "type": "stream",
            "cam_id": cam_id,
            "user_id": user_id,
        },
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises UnauthorizedError on expiry or invalid signature.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except JWTError as exc:
        raise UnauthorizedError("Invalid token") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    """Alias for decode_token for API access tokens."""
    payload = decode_token(token)
    if "user_id" not in payload:
        raise UnauthorizedError("Token missing user_id claim")
    return payload


def decode_stream_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a stream token specifically.
    Raises UnauthorizedError if token type is not 'stream'.
    """
    payload = decode_token(token)
    if payload.get("type") != "stream":
        raise UnauthorizedError("Not a stream token")
    return payload


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a refresh token.
    Returns (raw_token, token_hash).
    Store only the hash in the database — never the raw token.
    """
    from secrets import token_hex
    from hashlib import sha256

    raw = token_hex(64)  # 128 hex chars = 512 bits entropy
    hashed = sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    """Hash a raw refresh token for database lookup."""
    from hashlib import sha256

    return sha256(raw.encode()).hexdigest()
