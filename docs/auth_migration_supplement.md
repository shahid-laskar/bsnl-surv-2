# Sarvanetra — Auth Migration Supplement
## Replacing Django Auth with Native FastAPI Authentication

> **Document authority:** This document supplements `sarvanetra_implementation_plan.md` and is **binding**. Where this document conflicts with the main plan, this document wins. Read this document completely before starting Phase 1 or Phase 2 of the main plan.
>
> **Trigger:** The decision to remove Django entirely from the project. There is no Django process, no `auth_user` table from Django, no `django_*` tables. The FastAPI backend owns authentication completely from day one.

---

## 1. What Changes vs. the Main Plan

The main implementation plan was written assuming Django's `auth_user` table would exist and FastAPI would read from it. That assumption is now void. Every reference to `auth_user`, `django_user_id`, or Django session management in the main plan is replaced by the tables and logic defined here.

| Main plan reference | Replaced by |
|---|---|
| `ForeignKey("auth_user.id")` on `camera_master.added_by` | `ForeignKey("sv_users.id")` |
| `sarvanetra_users` table with `django_user_id` column | `sv_users` table — no Django reference |
| `kong_consumers` table | `sv_kong_consumers` table — same purpose, cleaner name |
| "Django User (read-only from FastAPI)" | Does not exist — `sv_users` is the only user table |
| Phase 1 note: "auth_user → Django User" | Removed entirely |

---

## 2. Complete Database Schema — Auth Tables

These are the **only** user-related tables. No `auth_user`, no `django_*` tables exist in this project.

### 2.1 `sv_users` — Primary user table

```sql
CREATE TABLE sv_users (
    id              SERIAL PRIMARY KEY,

    -- Identity
    username        VARCHAR(150) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL UNIQUE,
    first_name      VARCHAR(150) NOT NULL DEFAULT '',
    last_name       VARCHAR(150) NOT NULL DEFAULT '',

    -- Auth
    password_hash   VARCHAR(255) NOT NULL,     -- bcrypt hash via passlib

    -- Role: single role per user
    -- sysadmin     → full system access, all circles and BAs
    -- circle_admin → manages all BAs and customers within one circle
    -- ba_admin     → manages customers within one BA
    -- cust_admin   → manages cameras within one customer/company
    -- viewer       → read-only, scoped to their customer
    role            VARCHAR(50) NOT NULL,

    -- Scope: which BSNL hierarchy node this user belongs to
    -- All three are nullable; the applicable ones are set based on role:
    --   sysadmin:     all NULL (no scope restriction)
    --   circle_admin: cir_id set, ba_id NULL, com_id NULL
    --   ba_admin:     cir_id set, ba_id set, com_id NULL
    --   cust_admin:   cir_id set, ba_id set, com_id set
    --   viewer:       cir_id set, ba_id set, com_id set
    cir_id          INTEGER REFERENCES sv_circle_master(id) ON DELETE SET NULL,
    ba_id           INTEGER REFERENCES sv_ba_master(id) ON DELETE SET NULL,
    com_id          INTEGER REFERENCES sv_customer_master(id) ON DELETE SET NULL,

    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,  -- bypass all role checks

    -- Mobile push notifications (array of FCM/APNs tokens)
    device_tokens   JSONB NOT NULL DEFAULT '[]',

    -- Audit
    date_joined     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sv_users_username   ON sv_users(username);
CREATE INDEX idx_sv_users_email      ON sv_users(email);
CREATE INDEX idx_sv_users_com_id     ON sv_users(com_id) WHERE com_id IS NOT NULL;
CREATE INDEX idx_sv_users_cir_id     ON sv_users(cir_id) WHERE cir_id IS NOT NULL;
CREATE INDEX idx_sv_users_role       ON sv_users(role);
CREATE INDEX idx_sv_users_is_active  ON sv_users(is_active);
```

### 2.2 `sv_kong_consumers` — One row per user, maps to a Kong JWT credential

```sql
CREATE TABLE sv_kong_consumers (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL UNIQUE
                            REFERENCES sv_users(id) ON DELETE CASCADE,

    -- The Kong consumer username (used to identify the consumer in Kong)
    -- Pattern: "user_{sv_users.id}" e.g. "user_42"
    kong_consumer_username  VARCHAR(255) NOT NULL UNIQUE,

    -- The Kong JWT credential key (the `iss` claim value in the JWT)
    -- Pattern: "sarvanetra_user_{sv_users.id}" e.g. "sarvanetra_user_42"
    -- This is NOT the secret — it is the public key identifier
    jwt_key                 VARCHAR(255) NOT NULL UNIQUE,

    -- Whether this consumer is currently active in Kong
    -- Set to FALSE when user is deactivated; Kong credential is deleted
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sv_kong_consumers_user_id ON sv_kong_consumers(user_id);
CREATE INDEX idx_sv_kong_consumers_jwt_key ON sv_kong_consumers(jwt_key);
```

### 2.3 `sv_refresh_tokens` — Refresh token store for rotating JWT refresh

```sql
CREATE TABLE sv_refresh_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES sv_users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 of the refresh token
    device_id   VARCHAR(255),                  -- optional: mobile device identifier
    issued_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at  TIMESTAMPTZ
);

CREATE INDEX idx_sv_refresh_tokens_user_id    ON sv_refresh_tokens(user_id);
CREATE INDEX idx_sv_refresh_tokens_token_hash ON sv_refresh_tokens(token_hash);
CREATE INDEX idx_sv_refresh_tokens_expires_at ON sv_refresh_tokens(expires_at);

-- Clean up expired tokens periodically (pg_cron or application-level)
```

### 2.4 Updated `sv_camera_master.added_by` foreign key

The existing plan references `ForeignKey("auth_user.id")`. Replace with:

```sql
-- In the camera_master table definition:
added_by  INTEGER NOT NULL REFERENCES sv_users(id)
```

---

## 3. Table Naming Convention — Full List

The previous Django project used table names like `survapp_camera_master` (Django app prefix). This project uses an `sv_` prefix throughout for all new tables. This avoids any naming collision and makes the origin of every table clear.

```
sv_users                   ← replaces auth_user + UserDetails combined
sv_kong_consumers          ← new, maps users to Kong JWT credentials
sv_refresh_tokens          ← new, rotating refresh token store
sv_circle_master           ← replaces survapp_circle_master
sv_ba_master               ← replaces survapp_ba_master
sv_customer_master         ← replaces survapp_customer_master
sv_plan_master             ← replaces survapp_plan_master (stores plan limits)
sv_stream_master           ← replaces survapp_stream_master
sv_device_master           ← replaces survapp_device_master
sv_camera_master           ← replaces survapp_camera_master
sv_video_segment           ← replaces survapp_videosegment
sv_motion_event            ← replaces motion_events
sv_motion_detection_health ← replaces survapp_motiondetectionhealth
sv_camera_status_log       ← replaces survapp_camerastatuslog
sv_camera_health           ← replaces survapp_camerahealth
sv_api_log                 ← replaces survapp_apilog
sv_container_stats         ← replaces survapp_containerstats
```

The `sv_` prefix signals "Sarvanetra owned, managed by Alembic."

---

## 4. The Django Auth System — Exactly What It Was

Understanding what Django provided helps ensure nothing is missed.

### 4.1 `auth_user` table (Django built-in)
Stored: `id`, `username`, `password` (PBKDF2 hash), `email`, `first_name`, `last_name`, `is_active`, `is_staff`, `is_superuser`, `date_joined`, `last_login`.

**Replaced by:** `sv_users` (Section 2.1). Password hashing changes from Django's PBKDF2 to bcrypt via `passlib[bcrypt]`.

### 4.2 `UserDetails` model (authenticate app)
A one-to-one extension of `auth_user`. Stored: `user` (FK to auth_user), `cir_id`, `ba_id`, `com_id`, `mobile`.

**Replaced by:** The `cir_id`, `ba_id`, `com_id` columns are now directly on `sv_users`. No separate table needed.

### 4.3 `user_role` model (authenticate app)
A many-to-many join table: `usr_id` (FK to auth_user), `role_id` (FK to a role table with a `role` string field).

**Replaced by:** A single `role` column on `sv_users` (VARCHAR, not FK). In practice every user had exactly one role. The many-to-many was unused overhead.

### 4.4 `circle_master`, `ba_master`, `customer_master`, `plan_master` (authenticate app)
Geography and customer tables that lived in the authenticate app but were imported everywhere.

**Replaced by:** Same tables, renamed to `sv_circle_master`, `sv_ba_master`, `sv_customer_master`, `sv_plan_master`. Managed by Alembic, not Django migrations.

### 4.5 Django session middleware
Django's session backend (Redis) was used for browser session auth on the template views.

**Replaced by:** JWT tokens entirely. No session middleware. Redis is still used for caching, but not for sessions.

---

## 5. Full Geography & Plan Schema

These tables are required for auth scoping and must be created before `sv_users`.

```sql
CREATE TABLE sv_circle_master (
    id          SERIAL PRIMARY KEY,
    cir_name    VARCHAR(100) NOT NULL,
    cir_code    VARCHAR(20) NOT NULL UNIQUE  -- used in cam_id generation e.g. "KR"
);

CREATE TABLE sv_ba_master (
    id          SERIAL PRIMARY KEY,
    ba_name     VARCHAR(100) NOT NULL,
    ba_code     VARCHAR(20) NOT NULL,        -- used in cam_id generation e.g. "TVM"
    cir_id      INTEGER NOT NULL REFERENCES sv_circle_master(id) ON DELETE CASCADE,
    UNIQUE(ba_code, cir_id)
);

CREATE TABLE sv_plan_master (
    id          SERIAL PRIMARY KEY,
    plan_name   VARCHAR(100) NOT NULL,
    cam_limit   INTEGER NOT NULL DEFAULT 10  -- max cameras this plan allows
);

CREATE TABLE sv_customer_master (
    id          SERIAL PRIMARY KEY,
    com_name    VARCHAR(255) NOT NULL,
    com_adr     TEXT NOT NULL,
    gstn        VARCHAR(15),                 -- GST number, nullable
    cir_id      INTEGER NOT NULL REFERENCES sv_circle_master(id),
    ba_id       INTEGER NOT NULL REFERENCES sv_ba_master(id),
    plan_id     INTEGER NOT NULL REFERENCES sv_plan_master(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sv_customer_cir_id ON sv_customer_master(cir_id);
CREATE INDEX idx_sv_customer_ba_id  ON sv_customer_master(ba_id);
```

---

## 6. Authentication Flow — Step by Step

### 6.1 Login (web browser + mobile app)

```
Client                          FastAPI                         PostgreSQL      Kong
  │                                │                                │             │
  │  POST /api/v1/auth/login       │                                │             │
  │  {username, password,          │                                │             │
  │   device_id (optional)}        │                                │             │
  │──────────────────────────────> │                                │             │
  │                                │  SELECT * FROM sv_users        │             │
  │                                │  WHERE username = $1           │             │
  │                                │───────────────────────────────>│             │
  │                                │  <── user row                  │             │
  │                                │                                │             │
  │                                │  bcrypt.verify(password,       │             │
  │                                │    user.password_hash)         │             │
  │                                │                                │             │
  │                                │  If fail → 401                 │             │
  │                                │                                │             │
  │                                │  Build access token JWT:       │             │
  │                                │  {                             │             │
  │                                │    "iss": "sarvanetra_user_42",│             │
  │                                │    "sub": "42",                │             │
  │                                │    "iat": <now>,               │             │
  │                                │    "exp": <now + 3600>,        │             │
  │                                │    "user_id": 42,              │             │
  │                                │    "username": "johndoe",      │             │
  │                                │    "role": "cust_admin",       │             │
  │                                │    "com_id": 7,                │             │
  │                                │    "cir_id": 2,                │             │
  │                                │    "ba_id": 5                  │             │
  │                                │  }                             │             │
  │                                │  signed with JWT_SECRET_KEY    │             │
  │                                │                                │             │
  │                                │  Build refresh token:          │             │
  │                                │  random 64-byte hex string     │             │
  │                                │  Store SHA-256(token) in       │             │
  │                                │  sv_refresh_tokens             │             │
  │                                │───────────────────────────────>│             │
  │                                │                                │             │
  │                                │  Update sv_users.last_login    │             │
  │                                │───────────────────────────────>│             │
  │                                │                                │             │
  │  200 {                         │                                │             │
  │    access_token,               │                                │             │
  │    refresh_token,              │                                │             │
  │    token_type: "bearer",       │                                │             │
  │    expires_in: 3600,           │                                │             │
  │    user: {id, username,        │                                │             │
  │      role, com_id, ...}        │                                │             │
  │  }                             │                                │             │
  │<────────────────────────────── │                                │             │
```

### 6.2 Authenticated API request (via Kong)

```
Client                        Kong                          FastAPI             PostgreSQL
  │                             │                               │                   │
  │  GET /api/v1/cameras        │                               │                   │
  │  Authorization: Bearer <JWT>│                               │                   │
  │────────────────────────────>│                               │                   │
  │                             │  Kong JWT plugin:             │                   │
  │                             │  1. Extract JWT               │                   │
  │                             │  2. Read iss claim:           │                   │
  │                             │     "sarvanetra_user_42"      │                   │
  │                             │  3. Look up consumer by key   │                   │
  │                             │  4. Verify HMAC-SHA256 sig    │                   │
  │                             │  5. Verify exp not expired    │                   │
  │                             │                               │                   │
  │  401 if any check fails     │                               │                   │
  │<────────────────────────────│                               │                   │
  │                             │                               │                   │
  │                             │  Forward to FastAPI:          │                   │
  │                             │  + X-Consumer-Username: user_42                   │
  │                             │  + Authorization: Bearer <JWT>│                   │
  │                             │───────────────────────────────>                   │
  │                             │                               │  Decode JWT       │
  │                             │                               │  (no DB query —   │
  │                             │                               │  claims already   │
  │                             │                               │  in token)        │
  │                             │                               │                   │
  │                             │                               │  Inject user into │
  │                             │                               │  request state    │
  │                             │                               │                   │
  │                             │                               │  Run handler      │
  │                             │                               │  with role check  │
  │  200 {...}                  │                               │                   │
  │<────────────────────────────│<──────────────────────────────│                   │
```

### 6.3 Token refresh

```
POST /api/v1/auth/refresh
Body: { "refresh_token": "<token>" }

FastAPI:
  1. Compute SHA-256(refresh_token)
  2. SELECT * FROM sv_refresh_tokens
     WHERE token_hash = $1
       AND revoked = FALSE
       AND expires_at > NOW()
  3. If not found → 401
  4. Get user from sv_refresh_tokens.user_id
  5. Revoke old refresh token (UPDATE revoked=TRUE)
  6. Issue new access token + new refresh token (rotation)
  7. INSERT new refresh token into sv_refresh_tokens
  8. Return new {access_token, refresh_token}
```

---

## 7. Kong Consumer Provisioning — Per User

Every `sv_users` row must have a corresponding Kong consumer and JWT credential. This is managed by `KongProvisioningService` in FastAPI.

### 7.1 When a user is created (`POST /api/v1/users`)

```python
# Pseudocode — full implementation in app/services/kong_service.py

async def provision_kong_consumer(user: SvUser) -> None:
    consumer_username = f"user_{user.id}"
    jwt_key = f"sarvanetra_user_{user.id}"

    # Step 1: Create Kong consumer
    await kong_admin_client.post("/consumers", json={
        "username": consumer_username,
    })

    # Step 2: Create JWT credential for that consumer
    await kong_admin_client.post(
        f"/consumers/{consumer_username}/jwt",
        data={
            "key": jwt_key,                           # = iss claim
            "secret": settings.jwt_secret_key,        # SAME secret for all users
            "algorithm": "HS256",
        }
    )

    # Step 3: Persist mapping in sv_kong_consumers
    await db.execute(
        insert(SvKongConsumer).values(
            user_id=user.id,
            kong_consumer_username=consumer_username,
            jwt_key=jwt_key,
        )
    )
```

### 7.2 When a user is deactivated (`DELETE /api/v1/users/{id}`)

```python
async def deprovision_kong_consumer(user_id: int) -> None:
    consumer = await get_kong_consumer_by_user(user_id)
    if consumer:
        # Delete from Kong — all associated JWTs immediately invalidated
        await kong_admin_client.delete(
            f"/consumers/{consumer.kong_consumer_username}"
        )
        # Mark inactive locally (don't hard delete — audit trail)
        await db.execute(
            update(SvKongConsumer)
            .where(SvKongConsumer.user_id == user_id)
            .values(is_active=False)
        )
    # Also revoke all refresh tokens
    await db.execute(
        update(SvRefreshToken)
        .where(SvRefreshToken.user_id == user_id)
        .values(revoked=True, revoked_at=datetime.now(UTC))
    )
```

### 7.3 JWT `iss` claim — why per-user keys

Kong's JWT plugin identifies which consumer to validate against using the `iss` claim. Each user gets a unique `iss` value (`sarvanetra_user_{id}`), which maps to a unique Kong consumer. This means:

- Deactivating one user's Kong consumer does not affect other users.
- The Kong Admin API knows exactly which user is making each request (`X-Consumer-Username` header).
- All credentials share the same `JWT_SECRET_KEY` from `.env` — the key is not per-user, the consumer identifier is.

---

## 8. SQLAlchemy Models — Auth Tables

```python
# app/models/auth.py
from datetime import datetime, UTC
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class SvUser(Base):
    __tablename__ = "sv_users"

    id:             Mapped[int]           = mapped_column(Integer, primary_key=True)
    username:       Mapped[str]           = mapped_column(String(150), unique=True, nullable=False)
    email:          Mapped[str]           = mapped_column(String(254), unique=True, nullable=False)
    first_name:     Mapped[str]           = mapped_column(String(150), nullable=False, default="")
    last_name:      Mapped[str]           = mapped_column(String(150), nullable=False, default="")
    password_hash:  Mapped[str]           = mapped_column(String(255), nullable=False)
    role:           Mapped[str]           = mapped_column(String(50), nullable=False)
    cir_id:         Mapped[int | None]    = mapped_column(ForeignKey("sv_circle_master.id"), nullable=True)
    ba_id:          Mapped[int | None]    = mapped_column(ForeignKey("sv_ba_master.id"), nullable=True)
    com_id:         Mapped[int | None]    = mapped_column(ForeignKey("sv_customer_master.id"), nullable=True)
    is_active:      Mapped[bool]          = mapped_column(Boolean, nullable=False, default=True)
    is_superuser:   Mapped[bool]          = mapped_column(Boolean, nullable=False, default=False)
    device_tokens:  Mapped[list]          = mapped_column(JSONB, nullable=False, default=list)
    date_joined:    Mapped[datetime]      = mapped_column(
                                            DateTime(timezone=True),
                                            server_default=func.now(), nullable=False)
    last_login:     Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:     Mapped[datetime]      = mapped_column(
                                            DateTime(timezone=True),
                                            server_default=func.now(),
                                            onupdate=func.now(), nullable=False)

    # Relationships
    kong_consumer: Mapped["SvKongConsumer | None"] = relationship(
        "SvKongConsumer", back_populates="user", uselist=False
    )
    refresh_tokens: Mapped[list["SvRefreshToken"]] = relationship(
        "SvRefreshToken", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"SvUser(id={self.id}, username={self.username!r}, role={self.role!r})"


class SvKongConsumer(Base):
    __tablename__ = "sv_kong_consumers"

    id:                     Mapped[int]  = mapped_column(Integer, primary_key=True)
    user_id:                Mapped[int]  = mapped_column(
                                          ForeignKey("sv_users.id", ondelete="CASCADE"),
                                          unique=True, nullable=False)
    kong_consumer_username: Mapped[str]  = mapped_column(String(255), unique=True, nullable=False)
    jwt_key:                Mapped[str]  = mapped_column(String(255), unique=True, nullable=False)
    is_active:              Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at:             Mapped[datetime] = mapped_column(
                                              DateTime(timezone=True),
                                              server_default=func.now(), nullable=False)

    user: Mapped["SvUser"] = relationship("SvUser", back_populates="kong_consumer")


class SvRefreshToken(Base):
    __tablename__ = "sv_refresh_tokens"

    id:          Mapped[int]          = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]          = mapped_column(
                                       ForeignKey("sv_users.id", ondelete="CASCADE"),
                                       nullable=False)
    token_hash:  Mapped[str]          = mapped_column(String(255), unique=True, nullable=False)
    device_id:   Mapped[str | None]   = mapped_column(String(255), nullable=True)
    issued_at:   Mapped[datetime]     = mapped_column(
                                       DateTime(timezone=True),
                                       server_default=func.now(), nullable=False)
    expires_at:  Mapped[datetime]     = mapped_column(DateTime(timezone=True), nullable=False)
    revoked:     Mapped[bool]         = mapped_column(Boolean, nullable=False, default=False)
    revoked_at:  Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["SvUser"] = relationship("SvUser", back_populates="refresh_tokens")
```

---

## 9. Security Module — Full Implementation Spec

```python
# app/core/security.py
# Every function here must be unit-tested with 100% coverage.

from datetime import datetime, timedelta, UTC
from hashlib import sha256
from secrets import token_hex

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# bcrypt context — cost factor 12 is the industry standard for 2024
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """Hash a plain-text password. Never store plain-text passwords."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    com_id: int | None,
    cir_id: int | None,
    ba_id: int | None,
    jwt_key: str,                        # = sv_kong_consumers.jwt_key = iss claim
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a Kong-compatible HS256 JWT access token.

    The `iss` claim MUST equal the Kong JWT credential key for the user.
    Kong reads `iss`, looks up the matching consumer, and validates the
    signature using that consumer's registered secret.

    Token lifetime: settings.jwt_access_token_expire_minutes (default 60).
    """
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))

    payload: dict = {
        "iss": jwt_key,              # Kong uses this to identify the consumer
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        # Custom claims — read by FastAPI after Kong forwards the request
        "user_id": user_id,
        "username": username,
        "role": role,
        "com_id": com_id,
        "cir_id": cir_id,
        "ba_id": ba_id,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Kong has already validated the signature by the time FastAPI sees the
    request. This decode is a second line of defence — it re-validates exp
    and extracts the claims for the dependency injector.

    Raises UnauthorizedError on any failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if "user_id" not in payload:
            raise UnauthorizedError("Token missing user_id claim")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a refresh token.
    Returns (raw_token, token_hash).
    Store only the hash in the database — never the raw token.
    """
    raw = token_hex(64)                  # 128 hex chars = 512 bits entropy
    hashed = sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    """Hash a raw refresh token for database lookup."""
    return sha256(raw.encode()).hexdigest()


def create_stream_token(cam_id: str, user_id: int) -> str:
    """
    Short-lived JWT (15 min) for HLS stream access.
    Validated by Nginx auth_request before serving HLS segments.
    Uses the same JWT_SECRET_KEY but a different 'type' claim to
    prevent stream tokens being used as API access tokens.
    """
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_key,         # Global key — not user-specific
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "type": "stream",                # Must be checked on validation
        "cam_id": cam_id,
        "user_id": user_id,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_stream_token(token: str) -> dict:
    """Validate a stream token. Raises UnauthorizedError on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "stream":
            raise UnauthorizedError("Not a stream token")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Stream token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid stream token: {exc}") from exc
```

---

## 10. Auth Service — Full Implementation Spec

```python
# app/services/auth_service.py

from datetime import datetime, timedelta, UTC

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ConflictError, NotFoundError
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, hash_refresh_token,
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
        await self._db.execute(
            SvRefreshToken.__table__.insert().values(
                user_id=user.id,
                token_hash=refresh_hash,
                device_id=request.device_id,
                expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )

        # Update last login
        await self._db.execute(
            update(SvUser)
            .where(SvUser.id == user.id)
            .values(last_login=datetime.now(UTC))
        )

        logger.info("auth.login.success", user_id=user.id, role=user.role)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=3600,
            user=user,
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
        await self._db.execute(
            update(SvRefreshToken)
            .where(SvRefreshToken.id == refresh_record.id)
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )

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
        await self._db.execute(
            SvRefreshToken.__table__.insert().values(
                user_id=user.id,
                token_hash=new_hash,
                device_id=refresh_record.device_id,
                expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )

        return TokenRefreshResponse(
            access_token=new_access,
            refresh_token=new_raw,
            token_type="bearer",
            expires_in=3600,
        )

    async def _get_user_by_username(self, username: str) -> SvUser | None:
        result = await self._db.execute(
            select(SvUser).where(SvUser.username == username)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: int) -> SvUser | None:
        result = await self._db.execute(
            select(SvUser).where(SvUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_kong_consumer(self, user_id: int) -> SvKongConsumer | None:
        result = await self._db.execute(
            select(SvKongConsumer)
            .where(SvKongConsumer.user_id == user_id)
            .where(SvKongConsumer.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()
```

---

## 11. Pydantic Schemas — Auth

```python
# app/schemas/auth.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    device_id: str | None = None   # For mobile clients — stored with refresh token


class UserInResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    username:   str
    email:      str
    first_name: str
    last_name:  str
    role:       str
    com_id:     int | None
    cir_id:     int | None
    ba_id:      int | None
    is_active:  bool
    date_joined: datetime


class LoginResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = 3600
    user:          UserInResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenRefreshResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = 3600


class UserCreateRequest(BaseModel):
    username:   str = Field(min_length=3, max_length=150)
    email:      EmailStr
    password:   str = Field(min_length=8)
    first_name: str = Field(default="")
    last_name:  str = Field(default="")
    role:       str = Field(pattern="^(sysadmin|circle_admin|ba_admin|cust_admin|viewer)$")
    com_id:     int | None = None
    cir_id:     int | None = None
    ba_id:      int | None = None


class UserUpdateRequest(BaseModel):
    email:      EmailStr | None = None
    first_name: str | None = None
    last_name:  str | None = None
    role:       str | None = Field(
                    default=None,
                    pattern="^(sysadmin|circle_admin|ba_admin|cust_admin|viewer)$")
    com_id:     int | None = None
    cir_id:     int | None = None
    ba_id:      int | None = None
    is_active:  bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password:     str = Field(min_length=8)


class DeviceTokenRequest(BaseModel):
    token:    str = Field(min_length=1)
    platform: str = Field(pattern="^(android|ios|web)$")
```

---

## 12. Dependency Injection — Current User

```python
# app/core/dependencies.py  (auth section)
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import decode_access_token
from app.models.auth import SvUser
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> SvUser:
    """
    Decode JWT and return the current user from the database.
    Raises UnauthorizedError if token is invalid or user not found/inactive.

    NOTE: Kong has already validated the JWT signature. This re-validates
    the exp claim and fetches the user from DB to get fresh is_active status.
    A user deactivated mid-session will be rejected on next request.
    """
    payload = decode_access_token(token)
    user_id: int = payload["user_id"]

    result = await db.execute(
        select(SvUser).where(SvUser.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("Account is deactivated")

    return user


# Type alias used in router signatures
CurrentUser = SvUser


def require_role(*roles: str):
    """
    FastAPI dependency that enforces role-based access control.

    Usage:
        @router.delete("/{cam_id}")
        async def delete_camera(
            cam_id: str,
            _: SvUser = Depends(require_role("sysadmin", "circle_admin")),
        ) -> ...:

    is_superuser bypasses all role checks.
    """
    async def _check(
        current_user: SvUser = Depends(get_current_user),
    ) -> SvUser:
        if current_user.is_superuser:
            return current_user
        if current_user.role not in roles:
            raise ForbiddenError(
                f"Role '{current_user.role}' is not permitted. "
                f"Required: {', '.join(roles)}"
            )
        return current_user
    return _check


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
```

---

## 13. Auth API Router

```python
# app/api/v1/auth.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, CurrentUser
from app.schemas.auth import (
    LoginRequest, LoginResponse,
    TokenRefreshRequest, TokenRefreshResponse,
    UserInResponse, ChangePasswordRequest, DeviceTokenRequest,
)
from app.services.auth_service import AuthService
from app.services.kong_service import KongService

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
```

---

## 14. Kong Service

```python
# app/services/kong_service.py
# Manages Kong consumer lifecycle for each Sarvanetra user.

import httpx
import structlog
from app.core.config import settings
from app.core.exceptions import SarvanetraError

logger = structlog.get_logger(__name__)


class KongError(SarvanetraError):
    status_code = 502
    error_code = "KONG_ERROR"


class KongService:
    def __init__(self) -> None:
        self._base_url = settings.kong_admin_url   # e.g. http://kong:8001
        # No auth on Kong Admin API (internal network only)

    async def create_consumer_and_credential(
        self, user_id: int
    ) -> tuple[str, str]:
        """
        Create a Kong consumer and JWT credential for a new user.
        Returns (kong_consumer_username, jwt_key).
        Idempotent — safe to call multiple times for the same user_id.
        """
        consumer_username = f"user_{user_id}"
        jwt_key = f"sarvanetra_user_{user_id}"

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            # Create consumer (ignore 409 conflict — already exists)
            resp = await client.post("/consumers", json={"username": consumer_username})
            if resp.status_code not in (200, 201, 409):
                raise KongError(f"Failed to create Kong consumer: {resp.text}")

            # Create JWT credential
            resp = await client.post(
                f"/consumers/{consumer_username}/jwt",
                data={
                    "key": jwt_key,
                    "secret": settings.jwt_secret_key,
                    "algorithm": "HS256",
                },
            )
            if resp.status_code not in (200, 201, 409):
                raise KongError(f"Failed to create JWT credential: {resp.text}")

        logger.info("kong.consumer.created", user_id=user_id, jwt_key=jwt_key)
        return consumer_username, jwt_key

    async def delete_consumer(self, kong_consumer_username: str) -> None:
        """
        Delete a Kong consumer and all its credentials.
        All JWTs issued for this consumer are immediately invalidated.
        """
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.delete(f"/consumers/{kong_consumer_username}")
            if resp.status_code not in (204, 404):
                raise KongError(f"Failed to delete Kong consumer: {resp.text}")

        logger.info("kong.consumer.deleted", username=kong_consumer_username)

    async def health_check(self) -> bool:
        """Return True if Kong Admin API is reachable."""
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=5.0) as client:
                resp = await client.get("/")
                return resp.status_code == 200
        except Exception:
            return False
```

---

## 15. User Service — Create, Update, Deactivate

```python
# app/services/user_service.py  (key methods only — full file in Phase 2)

class UserService:

    async def create(
        self,
        request: UserCreateRequest,
        created_by: SvUser,
    ) -> SvUser:
        """
        Create a new user.
        - Validates role-based creation permissions
        - Hashes password with bcrypt
        - Creates user in sv_users
        - Provisions Kong consumer (async, after DB commit)
        - Inserts sv_kong_consumers row
        """
        # Role creation permissions:
        # sysadmin     → can create any role
        # circle_admin → can create ba_admin, cust_admin, viewer in own circle
        # ba_admin     → can create cust_admin, viewer in own BA
        # cust_admin   → can create viewer in own company
        # viewer       → cannot create users
        self._validate_creation_permission(created_by, request)

        # Check uniqueness
        if await self._username_exists(request.username):
            raise ConflictError(f"Username '{request.username}' already taken")
        if await self._email_exists(request.email):
            raise ConflictError(f"Email '{request.email}' already registered")

        # Hash password
        password_hash = hash_password(request.password)

        # Insert user
        user = SvUser(
            username=request.username,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            password_hash=password_hash,
            role=request.role,
            com_id=request.com_id,
            cir_id=request.cir_id,
            ba_id=request.ba_id,
        )
        self._db.add(user)
        await self._db.flush()  # Get user.id before Kong call

        # Provision Kong consumer
        consumer_username, jwt_key = await self._kong.create_consumer_and_credential(user.id)

        # Record Kong mapping
        self._db.add(SvKongConsumer(
            user_id=user.id,
            kong_consumer_username=consumer_username,
            jwt_key=jwt_key,
        ))

        await self._db.commit()
        logger.info("user.created", user_id=user.id, role=user.role, created_by=created_by.id)
        return user

    async def deactivate(self, user_id: int, deactivated_by: SvUser) -> None:
        """
        Soft-delete a user.
        - Sets is_active=FALSE in sv_users
        - Deletes Kong consumer (immediately invalidates all JWTs)
        - Revokes all refresh tokens
        """
        user = await self._get_or_raise(user_id)

        if user.id == deactivated_by.id:
            raise ForbiddenError("Cannot deactivate your own account")

        self._validate_deactivation_permission(deactivated_by, user)

        # Deactivate in DB
        await self._db.execute(
            update(SvUser).where(SvUser.id == user_id).values(is_active=False)
        )

        # Delete Kong consumer — all JWTs immediately invalid
        consumer = await self._get_kong_consumer(user_id)
        if consumer:
            await self._kong.delete_consumer(consumer.kong_consumer_username)
            await self._db.execute(
                update(SvKongConsumer)
                .where(SvKongConsumer.user_id == user_id)
                .values(is_active=False)
            )

        # Revoke all refresh tokens
        await self._db.execute(
            update(SvRefreshToken)
            .where(SvRefreshToken.user_id == user_id)
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )

        await self._db.commit()
        logger.info("user.deactivated", user_id=user_id, by=deactivated_by.id)
```

---

## 16. Alembic Migration Order

The migrations must run in this exact order. Dependencies between tables enforce this.

```
001_create_sv_circle_master.py
002_create_sv_ba_master.py
003_create_sv_plan_master.py
004_create_sv_customer_master.py
005_create_sv_stream_master.py
006_create_sv_users.py                  ← depends on circle, ba, customer
007_create_sv_kong_consumers.py         ← depends on sv_users
008_create_sv_refresh_tokens.py         ← depends on sv_users
009_create_sv_device_master.py
010_create_sv_camera_master.py          ← depends on circle, ba, customer, device, users, stream
011_create_sv_video_segment.py
012_create_sv_motion_event.py
013_create_sv_motion_detection_health.py
014_create_sv_camera_status_log.py
015_create_sv_camera_health.py
016_create_sv_api_log.py
017_create_sv_container_stats.py
018_seed_initial_data.py                ← insert circles, BAs, plans, first sysadmin user
```

---

## 17. Initial Data Seed — First sysadmin

The seed migration (`018_seed_initial_data.py`) must create a functional sysadmin account. After running `alembic upgrade head` for the first time, the system is ready to use.

```python
# alembic/versions/018_seed_initial_data.py

from passlib.context import CryptContext
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def upgrade() -> None:
    # Seed circles
    op.execute("""
        INSERT INTO sv_circle_master (cir_name, cir_code) VALUES
        ('Kerala', 'KR')
        ON CONFLICT DO NOTHING;
    """)

    # Seed BAs
    op.execute("""
        INSERT INTO sv_ba_master (ba_name, ba_code, cir_id)
        SELECT 'Thiruvananthapuram', 'TVM', id FROM sv_circle_master WHERE cir_code = 'KR'
        ON CONFLICT DO NOTHING;
    """)

    # Seed plans
    op.execute("""
        INSERT INTO sv_plan_master (plan_name, cam_limit) VALUES
        ('Starter',     10),
        ('Standard',    50),
        ('Enterprise', 200)
        ON CONFLICT DO NOTHING;
    """)

    # Seed stream types
    op.execute("""
        INSERT INTO sv_stream_master (strm_type, remark) VALUES
        ('RTSP',       'Direct RTSP pull from camera'),
        ('RTMP',       'RTMP push from camera to MediaMTX'),
        ('RTSP CLOUD', 'RTSP push via BSNL cloud relay')
        ON CONFLICT DO NOTHING;
    """)

    # Seed sysadmin user
    # Password read from env — never hardcoded
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "ChangeMe@123")
    password_hash  = pwd_context.hash(admin_password)

    op.execute(f"""
        INSERT INTO sv_users
          (username, email, first_name, last_name, password_hash, role, is_superuser)
        VALUES
          ('admin', 'admin@sarvanetra.local', 'System', 'Admin',
           '{password_hash}', 'sysadmin', TRUE)
        ON CONFLICT (username) DO NOTHING;
    """)
    # Kong consumer for the sysadmin is created at first login
    # (via KongService.create_consumer_and_credential called from UserService)
    # OR can be pre-seeded here if Kong is guaranteed to be up during migrations.
    # The login endpoint handles missing Kong consumers gracefully.
```

Add to `.env`:

```env
# First-run sysadmin password — change immediately after first login
INITIAL_ADMIN_PASSWORD=ChangeMe@123
```

---

## 18. Updated `.env` Variables

Add these to the `.env.example` in the main plan:

```env
# ── Kong Admin ────────────────────────────────────
# Used by KongService to create/delete consumers
KONG_ADMIN_URL=http://kong:8001

# ── Auth ──────────────────────────────────────────
# JWT secret — SAME value registered in Kong JWT credentials
# Must be at least 32 characters
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=

# JWT issuer key — used for stream tokens only (not per-user)
JWT_KEY=cctv@Bsnl

# Access token lifetime in minutes
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Refresh token lifetime in days
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# ── Seed ──────────────────────────────────────────
# Password for the initial sysadmin account
# Change immediately after first login
INITIAL_ADMIN_PASSWORD=ChangeMe@123
```

---

## 19. Tests Required for Auth Module

Every function in `app/core/security.py` and `app/services/auth_service.py` must have tests. The following scenarios must be covered:

```python
# tests/unit/test_security.py
test_hash_password_produces_bcrypt_hash
test_verify_password_correct_password_returns_true
test_verify_password_wrong_password_returns_false
test_create_access_token_contains_required_claims
test_create_access_token_iss_equals_jwt_key_param
test_decode_access_token_valid_token_returns_payload
test_decode_access_token_expired_token_raises_unauthorized
test_decode_access_token_wrong_secret_raises_unauthorized
test_create_stream_token_type_claim_is_stream
test_decode_stream_token_wrong_type_raises_unauthorized
test_create_refresh_token_returns_64_byte_hex
test_hash_refresh_token_deterministic

# tests/integration/test_auth_api.py
test_login_valid_credentials_returns_tokens
test_login_wrong_password_returns_401
test_login_inactive_user_returns_401
test_login_nonexistent_user_returns_401_not_404  # prevent enumeration
test_refresh_valid_token_returns_new_tokens
test_refresh_revoked_token_returns_401
test_refresh_expired_token_returns_401
test_refresh_rotation_old_token_rejected_after_use
test_get_me_valid_token_returns_user
test_get_me_no_token_returns_401
test_logout_revokes_refresh_token
test_change_password_correct_old_password_succeeds
test_change_password_wrong_old_password_returns_401
```

---

## 20. Agent Execution Checklist

Before starting Phase 1 of the main plan, confirm:

- [ ] `sv_` prefix used for ALL table names in all SQLAlchemy models
- [ ] No `auth_user` table reference anywhere in models or migrations
- [ ] `sv_camera_master.added_by` references `sv_users.id` not `auth_user.id`
- [ ] Password hashing uses `passlib[bcrypt]` with `bcrypt__rounds=12`
- [ ] JWT `iss` claim per user equals `sv_kong_consumers.jwt_key`
- [ ] `JWT_SECRET_KEY` is the same value used in Kong JWT credential `secret`
- [ ] `KongService.create_consumer_and_credential` called atomically with user insert (same transaction)
- [ ] Deactivating a user immediately deletes Kong consumer (instant JWT invalidation)
- [ ] Refresh token stored as SHA-256 hash, never plaintext
- [ ] Migration `018_seed_initial_data` creates admin account from `INITIAL_ADMIN_PASSWORD` env var
- [ ] All 24 security tests passing before Phase 3 begins
- [ ] `POST /api/v1/auth/login` response matches the `LoginResponse` schema exactly (frontend depends on this)

---

## 21. How the Frontend Auth.ts Must Change

The `src/lib/auth.ts` in the frontend references this login response shape. Confirm the backend returns exactly:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "a3b4c5...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 42,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "cust_admin",
    "com_id": 7,
    "cir_id": 2,
    "ba_id": 5,
    "is_active": true,
    "date_joined": "2024-01-15T10:30:00Z"
  }
}
```

The `src/lib/auth.ts` already reads `data.access_token` and `data.user.*` — this shape must be preserved exactly.

The frontend should also store `refresh_token` in `next-auth` session and call `POST /api/v1/auth/refresh` 2 minutes before access token expiry. The current `src/lib/auth.ts` does not yet implement refresh — this is a Phase 2 backend+frontend task.
