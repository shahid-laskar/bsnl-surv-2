# tests/unit/test_security.py
import pytest
from datetime import UTC, datetime, timedelta
from jose import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_stream_token,
    decode_stream_token,
    create_refresh_token,
    hash_refresh_token,
)


def test_hash_password_produces_bcrypt_hash():
    pw = "secret123"
    h = hash_password(pw)
    assert h.startswith("$2b$") or h.startswith("$2a$")
    assert h != pw


def test_verify_password_correct_password_returns_true():
    pw = "secret123"
    h = hash_password(pw)
    assert verify_password(pw, h) is True


def test_verify_password_wrong_password_returns_false():
    pw = "secret123"
    h = hash_password(pw)
    assert verify_password("wrong", h) is False


def test_create_access_token_contains_required_claims():
    token = create_access_token(
        user_id=1,
        username="testuser",
        role="sysadmin",
        cir_id=2,
        ba_id=3,
        com_id=4,
    )
    payload = decode_access_token(token)
    assert payload["user_id"] == 1
    assert payload["username"] == "testuser"
    assert payload["role"] == "sysadmin"
    assert payload["cir_id"] == 2
    assert payload["ba_id"] == 3
    assert payload["com_id"] == 4
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_iss_equals_jwt_key_param():
    token = create_access_token(
        user_id=1,
        username="testuser",
        role="viewer",
        jwt_key="custom_iss",
    )
    payload = decode_access_token(token)
    assert payload["iss"] == "custom_iss"


def test_decode_access_token_valid_token_returns_payload():
    token = create_access_token(user_id=42, username="alice", role="ba_admin")
    payload = decode_access_token(token)
    assert payload["user_id"] == 42
    assert payload["username"] == "alice"


def test_decode_access_token_expired_token_raises_unauthorized():
    # Construct an expired payload manually
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_key,
        "iat": int((now - timedelta(minutes=70)).timestamp()),
        "exp": int((now - timedelta(minutes=10)).timestamp()),
        "user_id": 1,
        "type": "access",
    }
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in str(exc_info.value).lower()


def test_decode_access_token_wrong_secret_raises_unauthorized():
    # Construct a token signed with a different secret
    payload = {
        "iss": settings.jwt_key,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "user_id": 42,
    }
    token_wrong_sig = jwt.encode(
        payload, "wrong_secret_key_12345", algorithm=settings.jwt_algorithm
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token_wrong_sig)
    assert "invalid token" in str(exc_info.value).lower()


def test_create_stream_token_type_claim_is_stream():
    token = create_stream_token(cam_id="CAMKLTVM00001", user_id=9)
    payload = decode_stream_token(token)
    assert payload["type"] == "stream"
    assert payload["cam_id"] == "CAMKLTVM00001"
    assert payload["user_id"] == 9


def test_decode_stream_token_wrong_type_raises_unauthorized():
    # If we pass an access token to decode_stream_token, it should fail
    token = create_access_token(user_id=1, username="test", role="sysadmin")
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_stream_token(token)
    assert "not a stream token" in str(exc_info.value).lower()


def test_create_refresh_token_returns_64_byte_hex():
    raw, hashed = create_refresh_token()
    assert len(raw) == 128  # 64 bytes in hex is 128 characters
    assert len(hashed) == 64  # sha256 hex digest is 64 characters
    assert hashed == hash_refresh_token(raw)


def test_hash_refresh_token_deterministic():
    raw = "some_random_refresh_token_value"
    h1 = hash_refresh_token(raw)
    h2 = hash_refresh_token(raw)
    assert h1 == h2
