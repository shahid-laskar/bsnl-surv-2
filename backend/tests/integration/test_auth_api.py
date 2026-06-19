# tests/integration/test_auth_api.py
import pytest
from datetime import datetime, UTC, timedelta
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, create_refresh_token
from app.models.auth import SvUser, SvKongConsumer, SvRefreshToken
from app.models.geography import circle_master, ba_master
from app.models.customer import customer_master


@pytest.fixture
async def seeded_user(db_session: AsyncSession) -> SvUser:
    # Seed Circle
    circle = circle_master(cir_name="Kerala", cir_code="KR")
    db_session.add(circle)
    await db_session.flush()

    # Seed BA
    ba = ba_master(ba_name="Thiruvananthapuram", ba_code="TVM", cir_id=circle.id)
    db_session.add(ba)
    await db_session.flush()

    # Seed Customer
    customer = customer_master(com_name="Test Company", cir_id=circle.id, ba_id=ba.id, plan_id=None)
    db_session.add(customer)
    await db_session.flush()

    # Seed User
    user = SvUser(
        username="testuser",
        email="testuser@sarvanetra.local",
        first_name="Test",
        last_name="User",
        password_hash=hash_password("Password@123"),
        role="sysadmin",
        cir_id=circle.id,
        ba_id=ba.id,
        com_id=customer.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # Seed Kong Consumer
    kong = SvKongConsumer(
        user_id=user.id,
        kong_consumer_username="user_testuser",
        jwt_key="sarvanetra_user_testuser",
        is_active=True,
    )
    db_session.add(kong)
    await db_session.flush()

    await db_session.commit()
    return user


@pytest.mark.anyio
async def test_login_valid_credentials_returns_tokens(client: AsyncClient, seeded_user: SvUser):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Password@123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testuser"


@pytest.mark.anyio
async def test_login_wrong_password_returns_401(client: AsyncClient, seeded_user: SvUser):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "WrongPassword"},
    )
    assert resp.status_code == 401
    assert "invalid username or password" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_login_inactive_user_returns_401(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    # Set user to inactive
    await db_session.execute(
        update(SvUser).where(SvUser.id == seeded_user.id).values(is_active=False)
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Password@123"},
    )
    assert resp.status_code == 401
    assert "deactivated" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_login_nonexistent_user_returns_401_not_404(client: AsyncClient, seeded_user: SvUser):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "doesnotexist", "password": "Password@123"},
    )
    assert resp.status_code == 401
    assert "invalid username or password" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_refresh_valid_token_returns_new_tokens(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    raw_token, token_hash = create_refresh_token()
    refresh_record = SvRefreshToken(
        user_id=seeded_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(refresh_record)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.anyio
async def test_refresh_revoked_token_returns_401(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    raw_token, token_hash = create_refresh_token()
    refresh_record = SvRefreshToken(
        user_id=seeded_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        revoked=True,
    )
    db_session.add(refresh_record)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_token},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_refresh_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    raw_token, token_hash = create_refresh_token()
    refresh_record = SvRefreshToken(
        user_id=seeded_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(refresh_record)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_token},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_refresh_rotation_old_token_rejected_after_use(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    raw_token, token_hash = create_refresh_token()
    refresh_record = SvRefreshToken(
        user_id=seeded_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(refresh_record)
    await db_session.commit()

    # First refresh: succeeds
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_token},
    )
    assert resp.status_code == 200

    # Second refresh: fails (revoked during rotation)
    resp2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_token},
    )
    assert resp2.status_code == 401


@pytest.mark.anyio
async def test_get_me_valid_token_returns_user(client: AsyncClient, seeded_user: SvUser):
    # Log in first to get token
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Password@123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


@pytest.mark.anyio
async def test_get_me_no_token_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_logout_revokes_refresh_token(
    client: AsyncClient, db_session: AsyncSession, seeded_user: SvUser
):
    raw_token, token_hash = create_refresh_token()
    refresh_record = SvRefreshToken(
        user_id=seeded_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(refresh_record)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": raw_token},
    )
    assert resp.status_code == 204

    # Verify database state
    result = await db_session.execute(
        select(SvRefreshToken).where(SvRefreshToken.token_hash == token_hash)
    )
    updated_record = result.scalar_one()
    assert updated_record.revoked is True


@pytest.mark.anyio
async def test_change_password_correct_old_password_succeeds(
    client: AsyncClient, seeded_user: SvUser
):
    # Login to get token
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Password@123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Password@123", "new_password": "NewPassword@123"},
    )
    assert resp.status_code == 204

    # Try logging in with new password
    login_resp2 = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "NewPassword@123"},
    )
    assert login_resp2.status_code == 200


@pytest.mark.anyio
async def test_change_password_wrong_old_password_returns_401(
    client: AsyncClient, seeded_user: SvUser
):
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Password@123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "WrongPassword", "new_password": "NewPassword@123"},
    )
    assert resp.status_code == 401
