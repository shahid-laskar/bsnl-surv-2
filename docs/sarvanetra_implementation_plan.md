# Sarvanetra — FastAPI Rewrite: Comprehensive Implementation Plan
## Version 1.0 · Team of 3 · Docker Compose · Debian VM

> **Document purpose:** This is the canonical build specification for the full rewrite of the Sarvanetra surveillance platform using FastAPI. It supersedes all previous implementation plans. Every phase is self-contained and executable. Complete all acceptance criteria for Phase N before beginning Phase N+1.

---

## 1. Executive Summary

| Item | Decision |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Frontend | Next.js 14 App Router + TypeScript |
| Database | PostgreSQL 16 (existing BSNL schema, extended) |
| Auth | Kong API Gateway + JWT (HS256) |
| Streaming | MediaMTX (RTSP ingest → HLS delivery) |
| Storage | MinIO (S3-compatible object storage) |
| Message Bus | Apache Kafka (KRaft mode) |
| Cache | Redis 7 |
| Deployment | Docker Compose on Debian VM |
| Multi-tenancy | Database-level via `customer_master` (BSNL hierarchy) |
| Camera Protocol | ONVIF (Matrix SATATYA primary) |

**Team split (recommended):**
- **Dev A** — FastAPI backend, database, Kafka workers
- **Dev B** — Next.js frontend, Kong configuration
- **Dev C** — MediaMTX pipeline, ONVIF integration, MinIO, Docker Compose

---

## 2. Technology Stack — Industry Standards

### 2.1 Backend (FastAPI)

```
fastapi==0.115.x          # Core framework
uvicorn[standard]==0.32.x # ASGI server with uvloop
gunicorn==23.x            # Process manager for production
pydantic==2.9.x           # Data validation (V2 — NOT V1)
pydantic-settings==2.x    # Settings from environment
sqlalchemy==2.x           # ORM (async mode with asyncpg)
asyncpg==0.30.x           # Async PostgreSQL driver
alembic==1.14.x           # Database migrations
redis[hiredis]==5.x       # Redis client (async)
aiokafka==0.11.x          # Async Kafka producer/consumer
minio==7.x                # MinIO/S3 client
python-jose[cryptography] # JWT handling
passlib[bcrypt]           # Password hashing
httpx==0.27.x             # Async HTTP client (replaces requests)
tenacity==9.x             # Retry logic with exponential backoff
structlog==24.x           # Structured logging (JSON)
pytest==8.x               # Testing
pytest-asyncio==0.24.x    # Async test support
httpx                     # Test client for FastAPI
coverage==7.x             # Code coverage
ruff==0.7.x               # Linter + formatter (replaces black+flake8+isort)
mypy==1.13.x              # Static type checking
```

### 2.2 Frontend (Next.js)

```
next==14.x                # Framework (App Router)
typescript==5.x           # Strict mode
tailwindcss==3.x          # Styling
shadcn/ui                 # Component library (built on Radix UI)
tanstack/react-query==5.x # Server state management
zustand==5.x              # Client state
hls.js==1.x               # HLS video playback
socket.io-client==4.x     # WebSocket (real-time alerts)
zod==3.x                  # Schema validation (mirrors backend Pydantic models)
next-auth==5.x            # Auth (JWT session)
axios==1.x                # HTTP client
eslint==9.x               # Linting
prettier==3.x             # Formatting
```

### 2.3 Infrastructure

```
PostgreSQL 16             # Primary database
Redis 7                   # Cache + session + rate limiting
Apache Kafka 3.7 (KRaft)  # Event bus (no ZooKeeper)
MinIO RELEASE.2024-xx     # Object storage
MediaMTX 1.x              # RTSP/HLS media server
Kong 3.8                  # API Gateway + JWT enforcement
Nginx                     # Reverse proxy + HLS delivery
Docker Compose v2         # Container orchestration
```

---

## 3. Repository Structure

```
sarvanetra/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI application factory
│   │   ├── core/
│   │   │   ├── config.py              # Settings (pydantic-settings)
│   │   │   ├── database.py            # Async SQLAlchemy engine + session
│   │   │   ├── security.py            # JWT creation/validation
│   │   │   ├── dependencies.py        # FastAPI dependency injection
│   │   │   ├── exceptions.py          # Custom exception hierarchy
│   │   │   └── logging.py             # structlog configuration
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # SQLAlchemy declarative base
│   │   │   ├── geography.py           # circle_master, ba_master
│   │   │   ├── customer.py            # customer_master
│   │   │   ├── device.py              # device_master
│   │   │   ├── camera.py              # camera_master
│   │   │   ├── stream.py              # stream_master
│   │   │   ├── recording.py           # VideoSegment
│   │   │   ├── motion.py              # motion_event, MotionDetectionHealth
│   │   │   ├── alert.py               # CameraStatusLog, CameraHealth
│   │   │   ├── plan.py                # plan_master
│   │   │   └── audit.py               # ApiLog
│   │   ├── schemas/                   # Pydantic V2 request/response models
│   │   │   ├── __init__.py
│   │   │   ├── common.py              # Pagination, standard responses
│   │   │   ├── auth.py
│   │   │   ├── geography.py
│   │   │   ├── customer.py
│   │   │   ├── camera.py
│   │   │   ├── device.py
│   │   │   ├── recording.py
│   │   │   ├── motion.py
│   │   │   └── alert.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py              # Main API router (v1 prefix)
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py            # Login, token refresh
│   │   │       ├── geography.py       # Circles, BAs
│   │   │       ├── customers.py       # Customer CRUD
│   │   │       ├── cameras.py         # Camera CRUD + stream URLs
│   │   │       ├── devices.py         # Device management
│   │   │       ├── recordings.py      # Video segment search + download
│   │   │       ├── motion.py          # Motion event history
│   │   │       ├── alerts.py          # Camera alerts + acknowledge
│   │   │       ├── streams.py         # Live stream token generation
│   │   │       ├── dashboard.py       # Dashboard stats
│   │   │       ├── users.py           # User management
│   │   │       ├── health.py          # /health endpoint
│   │   │       └── internal.py        # Internal endpoints (for MediaMTX/workers)
│   │   ├── services/                  # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── camera_service.py
│   │   │   ├── customer_service.py
│   │   │   ├── mediamtx_service.py    # MediaMTX API client
│   │   │   ├── minio_service.py       # MinIO operations
│   │   │   ├── kafka_service.py       # Kafka producer
│   │   │   ├── stream_service.py      # Stream token + HLS URL generation
│   │   │   ├── dashboard_service.py
│   │   │   └── notification_service.py # FCM push notifications
│   │   └── workers/                   # Background Kafka consumers
│   │       ├── __init__.py
│   │       ├── base_consumer.py       # Abstract consumer with DLQ + retry
│   │       ├── motion_consumer.py     # camera.motion → motion_event table
│   │       ├── status_consumer.py     # camera.status → CameraHealth table
│   │       ├── upload_worker.py       # recording.segments → MinIO + DB
│   │       └── onvif_producer.py      # ONVIF pull → camera.motion Kafka
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/                  # Migration files
│   ├── tests/
│   │   ├── conftest.py                # Fixtures (async DB, test client)
│   │   ├── unit/
│   │   │   ├── test_auth.py
│   │   │   ├── test_camera_service.py
│   │   │   └── test_stream_service.py
│   │   └── integration/
│   │       ├── test_auth_api.py
│   │       ├── test_camera_api.py
│   │       └── test_motion_flow.py
│   ├── pyproject.toml                 # Single config file: deps + ruff + mypy + pytest
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js 14 App Router
│   │   │   ├── (auth)/
│   │   │   │   └── login/page.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx           # Home: camera grid
│   │   │   │   ├── cameras/
│   │   │   │   │   ├── page.tsx
│   │   │   │   │   └── [id]/page.tsx
│   │   │   │   ├── recordings/page.tsx
│   │   │   │   ├── motion/page.tsx
│   │   │   │   ├── alerts/page.tsx
│   │   │   │   ├── users/page.tsx
│   │   │   │   ├── customers/page.tsx
│   │   │   │   └── settings/page.tsx
│   │   │   └── api/
│   │   │       └── auth/[...nextauth]/route.ts
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── cameras/
│   │   │   │   ├── CameraGrid.tsx
│   │   │   │   ├── CameraPlayer.tsx   # HLS.js wrapper
│   │   │   │   ├── CameraCard.tsx
│   │   │   │   └── CameraStatusBadge.tsx
│   │   │   ├── recordings/
│   │   │   │   ├── RecordingTable.tsx
│   │   │   │   └── RecordingPlayer.tsx
│   │   │   ├── motion/
│   │   │   │   └── MotionTimeline.tsx
│   │   │   ├── alerts/
│   │   │   │   ├── AlertList.tsx
│   │   │   │   └── AlertDrawer.tsx
│   │   │   └── layout/
│   │   │       ├── Sidebar.tsx
│   │   │       ├── TopBar.tsx
│   │   │       └── RoleGuard.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                 # Typed Axios wrapper
│   │   │   ├── auth.ts                # next-auth config
│   │   │   └── utils.ts
│   │   ├── hooks/
│   │   │   ├── useStreamToken.ts
│   │   │   └── useAlertSocket.ts
│   │   ├── stores/                    # Zustand stores
│   │   │   └── alertStore.ts
│   │   └── types/                     # TypeScript types (mirror Pydantic schemas)
│   │       └── api.ts
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── Dockerfile
├── workers/                           # Standalone Docker services
│   ├── onvif_producer/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── motion_consumer/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── upload_worker/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── status_monitor/
│       ├── main.py
│       ├── requirements.txt
│       └── Dockerfile
├── infra/
│   ├── kong/
│   │   └── setup-kong-jwt.sh
│   ├── mediamtx/
│   │   └── mediamtx.yml
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── conf.d/
│   └── postgres/
│       └── init-multiple-db.sh
├── docker-compose.yml                 # Development
├── docker-compose.prod.yml            # Production
├── .env.example
├── .gitignore
├── Makefile                           # Common dev commands
└── docs/
    ├── api.md
    ├── architecture.md
    ├── decisions.md
    └── runbook.md
```

---

## 4. Coding Standards — Non-Negotiable Rules

These rules apply to every file written. No exceptions.

### 4.1 Python / FastAPI Rules

**Rule 1: Async everywhere.**
Every endpoint, service method, and database call must be `async`. No `time.sleep()`, no synchronous DB calls inside async functions, no `requests` library (use `httpx`).

```python
# ✅ CORRECT
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)) -> CameraResponse:
    result = await db.execute(select(camera_master).where(camera_master.cam_id == camera_id))
    camera = result.scalar_one_or_none()
    if camera is None:
        raise CameraNotFoundError(camera_id)
    return CameraResponse.model_validate(camera)

# ❌ WRONG
def get_camera(camera_id: str):
    db = SessionLocal()
    camera = db.query(camera_master).filter_by(cam_id=camera_id).first()
    return camera
```

**Rule 2: Pydantic V2 models, strictly typed.**
Every API request and response uses a Pydantic V2 schema. No `dict` returns from endpoints. All fields annotated.

```python
# ✅ CORRECT
class CameraCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cam_name: str = Field(min_length=1, max_length=100)
    cam_loc: str = Field(min_length=1, max_length=300)
    cam_make: str = Field(min_length=1, max_length=100)
    cam_strm1: str = Field(pattern=r'^rtsp://')
    cam_usrname: str
    cam_pass: str = Field(min_length=1)
    com_id: int
    device_id: int
    strm_type_id: int
    cam_onvif: int | None = None
    is_active: bool = True
    motion_active: bool = False

class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cam_id: str
    cam_name: str
    cam_loc: str
    cam_make: str
    is_active: bool
    motion_active: bool
    created_at: datetime

# ❌ WRONG
@router.get("/cameras/{cam_id}")
async def get_camera(cam_id: str):
    ...
    return {"cam_id": cam_id, "name": camera.cam_name}  # Raw dict
```

**Rule 3: Service layer separation.**
Routers contain ONLY HTTP concerns (parsing request, calling service, returning response). Business logic lives in services. Database queries live in services or a separate repository layer.

```python
# ✅ CORRECT — router/v1/cameras.py
@router.post("/", response_model=CameraResponse, status_code=201)
async def create_camera(
    body: CameraCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    camera_service: CameraService = Depends(get_camera_service),
) -> CameraResponse:
    return await camera_service.create(body, created_by=current_user.id)

# ❌ WRONG — business logic in router
@router.post("/cameras/")
async def create_camera(body: dict, db: AsyncSession = Depends(get_db)):
    # DB query in router
    company = await db.execute(select(customer_master).where(...))
    camera = camera_master(cam_name=body["cam_name"], ...)
    db.add(camera)
    await db.commit()
    # MediaMTX call in router
    requests.post("http://mediamtx:9997/...")
    return camera
```

**Rule 4: Structured error handling.**
Custom exception classes. Never return `{"error": "something"}` manually. Use exception handlers.

```python
# app/core/exceptions.py
class SarvanetraError(Exception):
    """Base error for all application exceptions."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str, **kwargs: Any) -> None:
        self.detail = detail
        self.extra = kwargs
        super().__init__(detail)

class NotFoundError(SarvanetraError):
    status_code = 404
    error_code = "NOT_FOUND"

class CameraNotFoundError(NotFoundError):
    error_code = "CAMERA_NOT_FOUND"
    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Camera '{camera_id}' not found")

class UnauthorizedError(SarvanetraError):
    status_code = 401
    error_code = "UNAUTHORIZED"

class ForbiddenError(SarvanetraError):
    status_code = 403
    error_code = "FORBIDDEN"

class ConflictError(SarvanetraError):
    status_code = 409
    error_code = "CONFLICT"

# app/main.py — register exception handler
@app.exception_handler(SarvanetraError)
async def sarvanetra_exception_handler(
    request: Request, exc: SarvanetraError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
            }
        },
    )
```

**Rule 5: Dependency injection for everything cross-cutting.**
Auth, DB sessions, services — always injected, never imported globally.

```python
# app/core/dependencies.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserInDB:
    payload = verify_jwt_token(token)  # raises UnauthorizedError on failure
    user = await get_user_by_id(db, payload["user_id"])
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user

def require_role(*roles: str):
    """Role-based access control dependency."""
    async def _check(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if current_user.role not in roles:
            raise ForbiddenError(f"Role '{current_user.role}' cannot access this resource")
        return current_user
    return _check

# Usage in router:
@router.delete("/{cam_id}")
async def delete_camera(
    cam_id: str,
    _: UserInDB = Depends(require_role("sysadmin", "circle_admin")),
    service: CameraService = Depends(get_camera_service),
) -> dict[str, str]:
    await service.deactivate(cam_id)
    return {"message": "Camera deactivated"}
```

**Rule 6: Structured logging with structlog. No `print()`. No bare `logging.info()`.**

```python
# app/core/logging.py
import structlog

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

# Usage
logger = structlog.get_logger(__name__)

async def create_camera(data: CameraCreateRequest) -> CameraResponse:
    logger.info("camera.create.started", cam_name=data.cam_name, com_id=data.com_id)
    # ...
    logger.info("camera.create.success", cam_id=camera.cam_id)
    return CameraResponse.model_validate(camera)
```

**Rule 7: Settings from environment only. No hardcoded values anywhere.**

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Sarvanetra"
    debug: bool = False
    secret_key: str  # No default — must be in .env

    # Database
    database_url: str  # No default
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_key: str
    jwt_access_token_expire_minutes: int = 60

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_recordings_bucket: str = "recordings"
    minio_snapshots_bucket: str = "snapshots"
    minio_secure: bool = False

    # MediaMTX
    mediamtx_api_url: str = "http://mediamtx:9997"

    # FCM
    fcm_server_key: str | None = None

    # Domain
    domain_name: str = "localhost"
    host_ip: str = "127.0.0.1"

# Singleton
settings = Settings()
```

**Rule 8: All database models use SQLAlchemy 2.x mapped_column syntax.**

```python
# app/models/camera.py
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

class camera_master(Base):
    """
    Preserves existing BSNL naming convention for DB compatibility.
    All new models use this SQLAlchemy 2.x style.
    """
    __tablename__ = "survapp_camera_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cam_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    cam_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_loc: Mapped[str] = mapped_column(String(300), nullable=False)
    cam_make: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_usrname: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_pass: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_strm1: Mapped[str] = mapped_column(String(100), nullable=False)
    cam_strm2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cam_strm3: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    motion_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cam_onvif: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upd_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Foreign keys
    cir_id: Mapped[int] = mapped_column(ForeignKey("survapp_circle_master.id"), nullable=False)
    ba_id: Mapped[int] = mapped_column(ForeignKey("survapp_ba_master.id"), nullable=False)
    com_id: Mapped[int] = mapped_column(ForeignKey("survapp_customer_master.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("survapp_device_master.id"), nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("auth_user.id"), nullable=False)
    strm_type_id: Mapped[int | None] = mapped_column(ForeignKey("survapp_stream_master.id"), nullable=True)

    # Relationships
    circle: Mapped["circle_master"] = relationship("circle_master", back_populates="cameras")
    ba: Mapped["ba_master"] = relationship("ba_master", back_populates="cameras")
    customer: Mapped["customer_master"] = relationship("customer_master", back_populates="cameras")
    segments: Mapped[list["VideoSegment"]] = relationship("VideoSegment", back_populates="camera")
    motion_events: Mapped[list["motion_event"]] = relationship("motion_event", back_populates="camera")
```

**Rule 9: Tests for every service method. Minimum 80% coverage.**

```python
# tests/unit/test_camera_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_create_camera_generates_cam_id(
    camera_service: CameraService,
    mock_db: AsyncMock,
) -> None:
    """cam_id must be auto-generated if not provided."""
    request = CameraCreateRequest(
        cam_name="Test Camera",
        cam_loc="Main Gate",
        cam_make="Matrix",
        cam_strm1="rtsp://192.168.1.100/stream1",
        cam_usrname="admin",
        cam_pass="admin123",
        com_id=1,
        device_id=1,
        strm_type_id=1,
    )
    result = await camera_service.create(request, created_by=1)
    assert result.cam_id is not None
    assert result.cam_id.startswith("CAM")

@pytest.mark.asyncio
async def test_create_camera_raises_on_duplicate_stream(
    camera_service: CameraService,
    mock_db: AsyncMock,
) -> None:
    """Duplicate RTSP URL for same customer must raise ConflictError."""
    # ... setup existing camera in mock_db
    with pytest.raises(ConflictError, match="stream URL already registered"):
        await camera_service.create(duplicate_request, created_by=1)
```

**Rule 10: No raw SQL except in migrations. Use SQLAlchemy ORM or Core expressions.**

```python
# ✅ CORRECT
stmt = (
    select(camera_master)
    .where(camera_master.com_id == com_id)
    .where(camera_master.is_active == True)
    .order_by(camera_master.cam_name)
    .limit(page_size)
    .offset((page - 1) * page_size)
)
result = await db.execute(stmt)
cameras = result.scalars().all()

# ❌ WRONG
result = await db.execute(
    text("SELECT * FROM survapp_camera_master WHERE com_id = :com_id"),
    {"com_id": com_id}
)
```

### 4.2 Frontend (Next.js) Rules

**Rule 1: Server Components by default. Client Components only when needed.**
Data fetching, layout, static content → Server Components. Interactivity, browser APIs, real-time → Client Components.

**Rule 2: All API calls through a typed client.**

```typescript
// src/lib/api.ts
import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 10000,
});

// Auto-attach JWT from session
apiClient.interceptors.request.use((config) => {
  const token = getSessionToken();  // from next-auth session
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Typed API functions
export const cameraApi = {
  list: (params: CameraListParams) =>
    apiClient.get<PaginatedResponse<CameraResponse>>("/api/v1/cameras", { params }),

  get: (camId: string) =>
    apiClient.get<CameraResponse>(`/api/v1/cameras/${camId}`),

  create: (data: CameraCreateRequest) =>
    apiClient.post<CameraResponse>("/api/v1/cameras", data),

  getStreamToken: (camId: string) =>
    apiClient.get<StreamTokenResponse>(`/api/v1/cameras/${camId}/stream-token`),
};
```

**Rule 3: Zod for all form validation. Mirror backend Pydantic schemas.**

```typescript
// src/types/api.ts
import { z } from "zod";

export const CameraCreateSchema = z.object({
  cam_name: z.string().min(1).max(100),
  cam_loc: z.string().min(1).max(300),
  cam_make: z.string().min(1).max(100),
  cam_strm1: z.string().url().startsWith("rtsp://"),
  cam_usrname: z.string().min(1),
  cam_pass: z.string().min(1),
  com_id: z.number().int().positive(),
  device_id: z.number().int().positive(),
  strm_type_id: z.number().int().positive(),
  cam_onvif: z.number().int().optional(),
  is_active: z.boolean().default(true),
  motion_active: z.boolean().default(false),
});

export type CameraCreateRequest = z.infer<typeof CameraCreateSchema>;
```

**Rule 4: Role guard for every protected route.**

```typescript
// src/components/layout/RoleGuard.tsx
"use client";

import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";

interface RoleGuardProps {
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ roles, children, fallback }: RoleGuardProps) {
  const { data: session } = useSession();

  if (!session?.user?.role || !roles.includes(session.user.role)) {
    return fallback ?? <div>Access denied</div>;
  }

  return <>{children}</>;
}
```

---

## 5. Database Schema — Preserved BSNL Hierarchy

The existing Django migrations define the table names. We preserve them exactly for zero data-loss migration.

```
Table name mapping (Django → FastAPI/Alembic):
  survapp_circle_master    → circle_master model
  survapp_ba_master        → ba_master model
  survapp_customer_master  → customer_master model
  survapp_camera_master    → camera_master model
  survapp_device_master    → device_master model
  survapp_stream_master    → stream_master model
  survapp_videosegment     → VideoSegment model
  motion_events            → motion_event model  (existing custom table name)
  survapp_camerastatuslog  → CameraStatusLog model
  survapp_camerahealth     → CameraHealth model
  survapp_motiondetectionhealth → MotionDetectionHealth model
  survapp_apilog           → ApiLog model
  survapp_containerstats   → ContainerStats model
  auth_user                → Django User (read-only from FastAPI — users managed separately)
```

**Fixes applied during migration (not schema changes, just bug fixes):**

1. `VideoSegment.__str__` bug: `self.camera.camera_id` → `self.camera.cam_id`
2. `camera_master.save()` race condition: wrap in `SELECT FOR UPDATE` in service layer
3. `settings.py` duplicate `DATABASES` block: irrelevant, Django removed

**New tables added (Alembic migrations):**

```sql
-- Fast user auth table (replaces dependency on Django auth_user for API tokens)
CREATE TABLE sarvanetra_users (
    id          SERIAL PRIMARY KEY,
    django_user_id INTEGER UNIQUE REFERENCES auth_user(id),
    role        VARCHAR(50) NOT NULL,   -- sysadmin, circle_admin, ba_admin, cust_admin, viewer
    cir_id      INTEGER REFERENCES survapp_circle_master(id),
    ba_id       INTEGER REFERENCES survapp_ba_master(id),
    com_id      INTEGER REFERENCES survapp_customer_master(id),
    is_active   BOOLEAN DEFAULT TRUE,
    device_tokens JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Kong consumer mapping (one row per user, maps to Kong JWT consumer)
CREATE TABLE kong_consumers (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES sarvanetra_users(id) ON DELETE CASCADE,
    kong_consumer_username VARCHAR(255) UNIQUE NOT NULL,
    jwt_key     VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. API Design Standards

### 6.1 URL Conventions

```
Base path:  /api/v1/

Resources:  plural nouns, kebab-case
  GET     /api/v1/cameras                    # list
  POST    /api/v1/cameras                    # create
  GET     /api/v1/cameras/{cam_id}           # retrieve
  PATCH   /api/v1/cameras/{cam_id}           # partial update (use PATCH not PUT)
  DELETE  /api/v1/cameras/{cam_id}           # soft delete (is_active=False)

  GET     /api/v1/cameras/{cam_id}/stream-token   # sub-resource / action
  POST    /api/v1/cameras/{cam_id}/activate        # state-changing action
  POST    /api/v1/cameras/{cam_id}/deactivate

  GET     /api/v1/recordings?cam_id=X&start=Y&end=Z  # filtered list
  GET     /api/v1/motion-events?cam_id=X&date=Y       # filtered list

Internal:  /internal/  prefix (Nginx blocks from public)
  POST    /internal/stream-event
  POST    /internal/recording-complete
  POST    /internal/stream-health
  POST    /internal/camera-alerts
  POST    /internal/fcm-message

Health:
  GET     /health                            # liveness
  GET     /health/ready                      # readiness (checks DB + Redis)
```

### 6.2 Standard Response Shapes

```python
# Standard success list
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

# Standard error (from exception handler)
class ErrorResponse(BaseModel):
    error: ErrorDetail

class ErrorDetail(BaseModel):
    code: str
    message: str

# Standard HTTP status codes used
201 Created      → POST (create)
200 OK           → GET, PATCH
204 No Content   → DELETE
400 Bad Request  → Validation errors (Pydantic)
401 Unauthorized → Missing/invalid JWT
403 Forbidden    → Valid JWT, insufficient role
404 Not Found    → Resource doesn't exist
409 Conflict     → Duplicate resource
422 Unprocessable Entity → Business rule violation
500 Internal Server Error → Unexpected errors
```

### 6.3 Full API Endpoint List

```
AUTH
  POST   /api/v1/auth/login             # username + password → JWT token
  POST   /api/v1/auth/refresh           # refresh token
  GET    /api/v1/auth/me                # current user info

GEOGRAPHY
  GET    /api/v1/circles                # list circles (sysadmin)
  GET    /api/v1/circles/{id}/bas       # list BAs for circle
  GET    /api/v1/bas/{id}/customers     # list customers for BA

CUSTOMERS
  GET    /api/v1/customers              # role-filtered list
  POST   /api/v1/customers              # create (sysadmin, circle_admin)
  GET    /api/v1/customers/{id}
  PATCH  /api/v1/customers/{id}

CAMERAS
  GET    /api/v1/cameras                # role-filtered list
  POST   /api/v1/cameras                # create + auto-register in MediaMTX
  GET    /api/v1/cameras/{cam_id}
  PATCH  /api/v1/cameras/{cam_id}
  DELETE /api/v1/cameras/{cam_id}       # deactivate + remove from MediaMTX
  POST   /api/v1/cameras/{cam_id}/reactivate
  GET    /api/v1/cameras/{cam_id}/stream-token   # short-lived HLS token
  GET    /api/v1/cameras/{cam_id}/snapshot       # JPEG from MediaMTX
  GET    /api/v1/cameras/{cam_id}/health         # MediaMTX + motion health

DEVICES
  GET    /api/v1/devices                # list devices
  POST   /api/v1/devices                # register device (from edge device)
  GET    /api/v1/devices/{id}
  PATCH  /api/v1/devices/{id}           # update status / heartbeat

RECORDINGS
  GET    /api/v1/recordings             # ?cam_id=&start=&end=&page=
  GET    /api/v1/recordings/{id}
  GET    /api/v1/recordings/{id}/download # presigned MinIO URL
  POST   /api/v1/recordings/merge       # merge multiple segments (ffmpeg)
  POST   /api/v1/recordings/download-zip # zip multiple segments

MOTION EVENTS
  GET    /api/v1/motion-events          # ?cam_id=&date=&active_only=
  GET    /api/v1/motion-events/{id}

ALERTS
  GET    /api/v1/alerts                 # camera status alerts
  PATCH  /api/v1/alerts/{id}/acknowledge

DASHBOARD
  GET    /api/v1/dashboard/stats        # role-filtered stats
  GET    /api/v1/dashboard/camera-status # per-camera online/offline

USERS
  GET    /api/v1/users
  POST   /api/v1/users
  GET    /api/v1/users/{id}
  PATCH  /api/v1/users/{id}
  DELETE /api/v1/users/{id}
  POST   /api/v1/users/{id}/assign-role
  POST   /api/v1/users/me/device-token  # register FCM token

STREAM UTILITIES
  GET    /api/v1/streams/{cam_id}/hls-url   # full HLS URL for player
  POST   /api/v1/validate-stream-token      # token validation (for Nginx auth_request)

INTERNAL (Nginx-blocked from public)
  POST   /internal/stream-event
  POST   /internal/camera-alerts
  POST   /internal/fcm-message
  POST   /internal/recording-complete
  POST   /internal/stream-health
  POST   /internal/device-heartbeat
```

---

## 7. Kafka Topics & Worker Design

### 7.1 Topic Definitions

```
Topic                 Partitions  Retention  Purpose
─────────────────────────────────────────────────────────────────
camera.motion         6           7 days     ONVIF motion events
camera.status         6           7 days     Camera online/offline
recording.segments    6           48 hours   New video segments from MediaMTX
notification.fcm      3           24 hours   FCM push notification queue

Dead letter topics (auto-created by workers):
camera.motion.dlq
camera.status.dlq
recording.segments.dlq
```

### 7.2 Event Envelope (Standard for all topics)

```python
class KafkaEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any]

# camera.motion payload
class MotionEventPayload(BaseModel):
    camera_id: str
    is_motion: bool
    timestamp: datetime
    source: Literal["onvif"] = "onvif"
    data: dict[str, Any] = {}

# camera.status payload
class CameraStatusPayload(BaseModel):
    camera_id: str
    status: Literal["ready", "notReady"]
    timestamp: datetime
```

### 7.3 Base Worker Pattern

Every worker follows this pattern — no exceptions:

```python
# workers/base_consumer.py
class BaseKafkaConsumer(ABC):
    """
    Abstract base for all Kafka consumers.
    Enforces: manual commit, DLQ, structured logging, graceful shutdown.
    """

    def __init__(self, topic: str, group_id: str) -> None:
        self.topic = topic
        self.group_id = group_id
        self.logger = structlog.get_logger(self.__class__.__name__)
        self._running = False
        self._consumer: AIOKafkaConsumer | None = None
        self._dlq_producer: AIOKafkaProducer | None = None

    @abstractmethod
    async def process(self, event: KafkaEvent) -> None:
        """Process a single event. Raise on failure."""
        ...

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False,       # Manual commit ALWAYS
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        self._dlq_producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._consumer.start()
        await self._dlq_producer.start()
        self._running = True

        try:
            async for message in self._consumer:
                await self._handle_message(message)
        finally:
            await self._consumer.stop()
            await self._dlq_producer.stop()

    async def _handle_message(self, message: ConsumerRecord) -> None:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                event = KafkaEvent.model_validate(message.value)
                await self.process(event)
                await self._consumer.commit()           # Commit AFTER success
                self.logger.info(
                    "event.processed",
                    topic=self.topic,
                    event_type=event.event_type,
                    offset=message.offset,
                )
                return
            except Exception as exc:
                self.logger.warning(
                    "event.processing.failed",
                    attempt=attempt,
                    error=str(exc),
                    offset=message.offset,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)   # Exponential backoff
                else:
                    await self._send_to_dlq(message, str(exc))
                    await self._consumer.commit()       # Commit to skip poison pill

    async def _send_to_dlq(self, message: ConsumerRecord, error: str) -> None:
        dlq_topic = f"{self.topic}.dlq"
        dlq_payload = {
            "original_topic": self.topic,
            "original_offset": message.offset,
            "original_value": message.value,
            "error": error,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        await self._dlq_producer.send(dlq_topic, value=dlq_payload)
        self.logger.error("event.sent_to_dlq", topic=dlq_topic, error=error)
```

---

## 8. Docker Compose Architecture

### 8.1 Service Dependency Graph

```
postgres ─────────────────────────────────┐
redis ──────────────────────────────────┐ │
kafka ────────────────────────────────┐ │ │
minio ──────────────────────────────┐ │ │ │
                                    │ │ │ │
kong-migration ──────────(depends: postgres)
kong ────────────────────(depends: kong-migration + postgres)
                                    │
fastapi ──────────────────(depends: postgres + redis + kafka + kong)
                                    │
kong-config ──────────────(depends: kong + fastapi)
                                    │
mediamtx ─────────────────(depends: minio)
                                    │
nginx ─────────────────────(depends: fastapi + mediamtx + kong)
                                    │
onvif-producer ────────────(depends: postgres + kafka + fastapi)
motion-consumer ───────────(depends: postgres + kafka)
upload-worker ─────────────(depends: kafka + minio + postgres)
status-monitor ────────────(depends: kafka + fastapi + redis)
                                    │
frontend ──────────────────(depends: fastapi)
```

### 8.2 Port Allocation

```
Public-facing (via Nginx):
  80/443    Nginx (all traffic entry point)
  8888      HLS direct (Nginx proxy to MediaMTX)

Internal (Docker network only, not exposed to host):
  8000      FastAPI
  3000      Next.js frontend
  8001      Kong Admin API
  8554      MediaMTX RTSP
  9000      MinIO API
  9001      MinIO Console
  9092      Kafka
  5432      PostgreSQL
  6379      Redis

Debug only (exposed with profiles: ["debug"]):
  8080      Kafka UI
  9999      MediaMTX API (mapped)
  1935      RTMP
```

---

## 9. Implementation Phases

### Phase 0 — Project Scaffolding (Day 1–2)
**Owner: Dev A**

Tasks:
- Init git repository with the folder structure from Section 3
- Set up `pyproject.toml` with all dependencies (use `uv` as package manager — faster than pip)
- Configure `ruff` (lint + format), `mypy` (type check), `pytest` (testing) in `pyproject.toml`
- Set up `docker-compose.yml` with postgres, redis, kafka, minio, mediamtx stubs
- Configure pre-commit hooks: `ruff check`, `ruff format`, `mypy`, no-print check
- Create `.env.example` with all variables documented
- Create `Makefile` with: `make dev`, `make test`, `make lint`, `make migrate`
- Set up `alembic` connected to the existing database

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "ANN", "S", "B", "A", "COM", "C4", "DTZ", "LOG", "G"]
ignore = ["ANN101", "ANN102"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
omit = ["tests/*", "alembic/*"]
```

Acceptance criteria:
- [ ] `make lint` passes on empty project
- [ ] `make test` runs (zero tests, all pass)
- [ ] `docker compose up postgres redis` → both healthy
- [ ] `alembic current` connects to DB successfully
- [ ] Pre-commit hooks block a file with `print()` statement

---

### Phase 1 — Database Models & Migrations (Day 2–4)
**Owner: Dev A**

Tasks:
- Write all SQLAlchemy 2.x models mirroring existing Django tables exactly
- Write Alembic migration that creates tables compatible with existing schema
- Fix the `VideoSegment.__str__` bug at model level
- Add the `sarvanetra_users` and `kong_consumers` tables
- Add transaction-level camera ID generation (replace Django `save()` override)
- Write model-level unit tests

```python
# Migration strategy:
# If starting fresh (new DB): alembic creates all tables
# If migrating from existing Django DB: alembic runs in --check mode to verify compatibility
```

Acceptance criteria:
- [ ] `alembic upgrade head` on empty DB creates all tables
- [ ] All model relationships load without N+1 queries (test with `echo=True`)
- [ ] `camera_master` cam_id generation is race-condition-free (SELECT FOR UPDATE in service)
- [ ] All model `__repr__` methods defined (no `print()` in models)
- [ ] 100% mypy pass on all model files

---

### Phase 2 — FastAPI Core + Auth (Day 4–7)
**Owner: Dev A**

Tasks:
- `app/main.py` — application factory with lifespan, middleware, exception handlers
- `app/core/config.py` — Settings class
- `app/core/database.py` — async engine, session factory, dependency
- `app/core/security.py` — JWT generation/validation matching existing Kong configuration
- `app/core/exceptions.py` — full exception hierarchy
- `app/core/logging.py` — structlog configuration
- `app/core/dependencies.py` — `get_db`, `get_current_user`, `require_role`
- `app/api/v1/auth.py` — login, refresh, /me endpoints
- `app/api/v1/health.py` — `/health` and `/health/ready`
- Full test suite for auth flow

```python
# app/main.py — Application factory pattern
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await database.connect()
    await redis_client.ping()
    configure_logging()
    logger.info("app.started", version=APP_VERSION)
    yield
    # Shutdown
    await database.disconnect()
    await redis_client.close()
    logger.info("app.stopped")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Sarvanetra API",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,  # Disable docs in production
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,  # From env, not hardcoded
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(SarvanetraError, sarvanetra_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Register routers
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/internal")
    app.include_router(health_router)

    return app

app = create_app()
```

Acceptance criteria:
- [ ] `POST /api/v1/auth/login` returns JWT that Kong validates
- [ ] `GET /api/v1/auth/me` returns current user with role
- [ ] Invalid token → 401 with standard error shape
- [ ] Insufficient role → 403 with standard error shape
- [ ] `GET /health/ready` checks DB + Redis, returns 503 if either down
- [ ] OpenAPI schema auto-generated at `/docs` (debug mode only)
- [ ] All auth tests pass, 100% coverage on auth module

---

### Phase 3 — Camera & Customer APIs (Day 7–12)
**Owner: Dev A (backend) + Dev B (frontend starts)**

Backend tasks (Dev A):
- `app/services/camera_service.py` — full CRUD with MediaMTX integration
- `app/services/customer_service.py` — role-filtered CRUD
- `app/services/mediamtx_service.py` — async MediaMTX API client (httpx)
- `app/api/v1/cameras.py` — all camera endpoints
- `app/api/v1/customers.py` — all customer endpoints
- `app/api/v1/geography.py` — circles, BAs
- `app/api/v1/devices.py` — device registration and heartbeat
- Integration tests for all endpoints

```python
# app/services/mediamtx_service.py — example
class MediaMTXService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def add_rtsp_path(self, cam_id: str, rtsp_url: str) -> None:
        """Register a camera RTSP source with MediaMTX."""
        payload = {
            "source": rtsp_url,
            "record": True,
            "recordPath": f"/recordings/{cam_id}/%Y/%m/%d/%H-%M-%S-%f-%path",
            "recordFormat": "fmp4",
            "recordSegmentDuration": "20s",
        }
        response = await self._client.post(
            f"{settings.mediamtx_api_url}/v3/config/paths/add/live/{cam_id}",
            json=payload,
            timeout=10.0,
        )
        if response.status_code not in (200, 201):
            raise MediaMTXError(f"Failed to register camera {cam_id}: {response.text}")

    async def remove_path(self, cam_id: str) -> None:
        """Remove a camera path from MediaMTX."""
        response = await self._client.delete(
            f"{settings.mediamtx_api_url}/v3/config/paths/delete/live/{cam_id}",
            timeout=10.0,
        )
        # 404 is acceptable (path may not exist)
        if response.status_code not in (200, 204, 404):
            raise MediaMTXError(f"Failed to remove camera {cam_id}: {response.text}")

    async def get_active_paths(self) -> list[str]:
        """Get list of active (ready) stream paths."""
        response = await self._client.get(
            f"{settings.mediamtx_api_url}/v3/paths/list",
            timeout=10.0,
        )
        data = response.json()
        return [
            item["name"].split("/")[-1]
            for item in data.get("items", [])
            if item.get("ready") is True
        ]
```

Frontend tasks (Dev B — starts during Phase 3):
- Next.js 14 project setup with TypeScript strict mode
- shadcn/ui installation and theme configuration
- `src/lib/api.ts` — typed API client
- `src/app/(auth)/login/page.tsx` — login form
- `src/app/(dashboard)/layout.tsx` — sidebar + topbar shell
- `src/components/layout/Sidebar.tsx`
- `src/components/layout/RoleGuard.tsx`

Acceptance criteria:
- [ ] `POST /api/v1/cameras` creates camera AND registers in MediaMTX atomically
- [ ] `DELETE /api/v1/cameras/{id}` deactivates camera AND removes from MediaMTX
- [ ] Role filtering works: circle_admin only sees own circle's cameras
- [ ] Camera list supports pagination (`?page=1&page_size=25`)
- [ ] All endpoints return the standard response shape
- [ ] MediaMTX unavailable → 503 with meaningful error (does not crash app)
- [ ] Frontend login redirects to dashboard with JWT in session

---

### Phase 4 — Kong Configuration & Stream Tokens (Day 12–15)
**Owner: Dev B + Dev C**

Dev C tasks:
- Rewrite `setup-kong-jwt.sh` cleanly (using existing route structure)
- Kong services: FastAPI, MediaMTX API, MinIO, HLS stream
- JWT consumer matching existing `key=cctv@Bsnl` / `secret=Bsnl@9876` initially
- HLS stream route with JWT validation via Nginx `auth_request`
- Document Kong setup in `docs/architecture.md`

Dev A tasks:
- `app/api/v1/streams.py` — `GET /api/v1/cameras/{cam_id}/stream-token`
- `app/api/v1/streams.py` — `POST /validate-stream-token` (for Nginx auth_request)
- `app/services/stream_service.py` — JWT generation for stream tokens

```python
# Stream token: short-lived JWT (15 min) containing cam_id + user_id
# Nginx auth_request calls /validate-stream-token before serving HLS
# This replaces the existing validate_stream_token view in Django

class StreamTokenService:
    def generate(self, cam_id: str, user_id: int) -> StreamToken:
        now = datetime.now(UTC)
        payload = {
            "iss": settings.jwt_key,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "cam_id": cam_id,
            "user_id": user_id,
            "type": "stream",
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        return StreamToken(
            token=token,
            stream_url=f"http://{settings.domain_name}/stream/hls/{cam_id}/index.m3u8?token={token}",
            expires_at=now + timedelta(minutes=15),
        )

    def validate(self, token: str) -> StreamTokenPayload:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            if payload.get("type") != "stream":
                raise UnauthorizedError("Not a stream token")
            return StreamTokenPayload.model_validate(payload)
        except JWTError as exc:
            raise UnauthorizedError("Invalid stream token") from exc
```

Dev B tasks (frontend):
- `src/components/cameras/CameraPlayer.tsx` — HLS.js integration
- `src/hooks/useStreamToken.ts` — token fetch + 13-minute auto-refresh
- `src/app/(dashboard)/cameras/page.tsx` — camera list with status badges
- `src/app/(dashboard)/cameras/[id]/page.tsx` — single camera live view

```typescript
// src/hooks/useStreamToken.ts
export function useStreamToken(camId: string) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const fetchToken = async () => {
      const { data } = await cameraApi.getStreamToken(camId);
      setToken(data.token);
    };

    fetchToken();

    // Refresh 2 minutes before 15-minute expiry (every 13 minutes)
    const interval = setInterval(fetchToken, 13 * 60 * 1000);
    return () => clearInterval(interval);
  }, [camId]);

  return token;
}
```

Acceptance criteria:
- [ ] `GET /api/v1/cameras/{id}/stream-token` returns token + HLS URL
- [ ] Kong routes MediaMTX API calls with JWT validation
- [ ] Nginx serves HLS segments only after `/validate-stream-token` returns 200
- [ ] Expired stream token → 401 from Nginx
- [ ] HLS plays in browser via `CameraPlayer` component
- [ ] Token auto-refreshes without interrupting playback

---

### Phase 5 — Kafka Workers (Day 14–18)
**Owner: Dev C**

Tasks:
- `workers/base_consumer.py` — abstract base with manual commit + DLQ
- `workers/onvif_producer/` — ONVIF → Kafka producer (rewrite existing)
- `workers/motion_consumer/` — Kafka → `motion_event` table
- `workers/status_monitor/` — Kafka → `CameraHealth` table + FCM
- `workers/upload_worker/` — `recording.segments` → MinIO + DB
- Worker Dockerfiles with health endpoints

**Critical fixes from existing codebase:**

```python
# motion_consumer: was enable_auto_commit=True — CHANGED TO FALSE
# onvif_producer: was ThreadPoolExecutor — CHANGED TO asyncio tasks
# upload_worker: hardcoded DATABASE_URL — REMOVED, uses settings

# workers/onvif_producer/main.py — asyncio rewrite
class ONVIFEventProducer:
    async def monitor(self) -> None:
        """Single asyncio task per camera. No threads."""
        while self._running:
            if not self._subscription_address:
                await self._create_subscription()
                await asyncio.sleep(10)
                continue

            try:
                await self._pull_and_publish()
                self._consecutive_errors = 0
            except SubscriptionDeadError:
                self._subscription_address = None
            except Exception as exc:
                self._consecutive_errors += 1
                self.logger.warning("pull.failed", error=str(exc))
                if self._consecutive_errors >= 5:
                    self._subscription_address = None
                await asyncio.sleep(2 ** min(self._consecutive_errors, 5))

class MotionEventProducerWorker:
    async def start(self) -> None:
        """Manage all camera tasks via asyncio. No ThreadPoolExecutor."""
        self._semaphore = asyncio.Semaphore(50)  # Max 50 concurrent ONVIF connections
        while True:
            await self._sync_cameras()
            await asyncio.sleep(self._refresh_interval)

    async def _sync_cameras(self) -> None:
        current_cameras = await self._get_worker_cameras()
        current_ids = {c.cam_id for c in current_cameras}
        active_ids = set(self._tasks.keys())

        for cam_id in current_ids - active_ids:
            camera = next(c for c in current_cameras if c.cam_id == cam_id)
            task = asyncio.create_task(
                self._run_with_semaphore(camera),
                name=f"onvif-{cam_id}"
            )
            self._tasks[cam_id] = task

        for cam_id in active_ids - current_ids:
            self._tasks[cam_id].cancel()
            del self._tasks[cam_id]
```

Acceptance criteria:
- [ ] ONVIF producer: motion from Matrix SATATYA camera → `camera.motion` Kafka within 5s
- [ ] Motion consumer: `camera.motion` Kafka → `motion_event` DB row with correct timestamps
- [ ] Kill motion consumer mid-processing → restart → no events lost (manual commit)
- [ ] Status monitor: camera goes offline → `CameraHealth` updated → FCM sent
- [ ] Upload worker: segment file in `/recordings/` → MinIO upload → `VideoSegment` DB row
- [ ] All workers expose `GET /health` on port 8081 returning `{"status": "ok"}`
- [ ] DLQ: 3 processing failures → message in `camera.motion.dlq`

---

### Phase 6 — Recordings & Motion History APIs (Day 18–22)
**Owner: Dev A (backend) + Dev B (frontend)**

Backend tasks:
- `app/api/v1/recordings.py` — timeline data, segment serving, merge, zip download
- `app/api/v1/motion.py` — motion event history with timeline support
- `app/services/minio_service.py` — presigned URL generation, segment streaming
- Replace `ffmpeg subprocess` calls with `asyncio.create_subprocess_exec`

```python
# Async ffmpeg call — no blocking subprocess
async def merge_segments(segment_paths: list[str], output_path: str) -> None:
    concat_content = "\n".join(f"file '{p}'" for p in segment_paths)
    concat_file = Path(output_path).parent / "concat.txt"
    concat_file.write_text(concat_content)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", "-y", output_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise FFmpegError(f"Merge failed: {stderr.decode()}")
```

Frontend tasks:
- `src/app/(dashboard)/recordings/page.tsx` — date range filter + camera filter
- `src/components/recordings/RecordingTable.tsx`
- `src/components/recordings/RecordingPlayer.tsx` — with range request support
- `src/app/(dashboard)/motion/page.tsx` — motion event timeline
- `src/components/motion/MotionTimeline.tsx` — visual timeline

Acceptance criteria:
- [ ] `GET /api/v1/recordings?cam_id=X&start=Y&end=Z` returns paginated segments in IST
- [ ] `GET /api/v1/recordings/{id}/download` returns MinIO presigned URL (60-min TTL)
- [ ] `POST /api/v1/recordings/merge` merges segments via async ffmpeg, returns MP4
- [ ] `GET /api/v1/motion-events` returns events with duration calculated
- [ ] Recording player supports HTTP range requests for seeking
- [ ] Motion timeline renders in frontend with correct IST timestamps

---

### Phase 7 — Dashboard & Alerts (Day 22–26)
**Owner: Dev B (frontend) + Dev A (backend)**

Backend tasks:
- `app/api/v1/dashboard.py` — role-filtered stats (replaces monolithic `dashboard_stats` view)
- `app/api/v1/alerts.py` — camera alerts + acknowledge
- `app/services/dashboard_service.py` — MediaMTX status + DB aggregation
- WebSocket endpoint for real-time alerts

```python
# app/api/v1/dashboard.py
@router.get("/stats", response_model=DashboardStatsResponse)
async def dashboard_stats(
    current_user: UserInDB = Depends(get_current_user),
    camera_service: CameraService = Depends(get_camera_service),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> DashboardStatsResponse:
    # All filtering logic in service, not in router
    return await dashboard_service.get_stats(current_user)

# WebSocket for real-time alerts
@router.websocket("/ws/alerts")
async def alert_websocket(
    websocket: WebSocket,
    token: str,  # From query param
    redis: Redis = Depends(get_redis),
) -> None:
    # Validate token
    payload = stream_service.validate(token)
    await websocket.accept()

    pubsub = redis.pubsub()
    await pubsub.subscribe(f"alerts:{payload.user_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json(json.loads(message["data"]))
    except WebSocketDisconnect:
        await pubsub.unsubscribe()
```

Frontend tasks:
- `src/app/(dashboard)/page.tsx` — main dashboard with camera grid + stats
- `src/components/cameras/CameraGrid.tsx` — 2×2 to 4×4 live grid
- `src/app/(dashboard)/alerts/page.tsx`
- `src/components/alerts/AlertList.tsx` + `AlertDrawer.tsx`
- `src/hooks/useAlertSocket.ts` — WebSocket connection with auto-reconnect
- Dashboard stats cards (total cameras, online count, motion events today)

Acceptance criteria:
- [ ] Dashboard loads with correct camera counts per role
- [ ] Camera grid shows live HLS for all online cameras
- [ ] WebSocket alert fires in frontend within 3 seconds of camera going offline
- [ ] Alerts can be acknowledged (PATCH endpoint + UI)
- [ ] Dashboard MediaMTX query is cached in Redis (5-second TTL)

---

### Phase 8 — User Management (Day 26–28)
**Owner: Dev B**

Tasks:
- `app/api/v1/users.py` — user CRUD with role assignment
- Frontend user management pages
- `POST /api/v1/users/me/device-token` — FCM token registration

Acceptance criteria:
- [ ] sysadmin can create/deactivate any user
- [ ] circle_admin can only manage users in own circle
- [ ] cust_admin can only manage users in own company
- [ ] Role assignment enforced at DB level (not just frontend)
- [ ] FCM token stored in `sarvanetra_users.device_tokens`

---

### Phase 9 — Integration Testing & Hardening (Day 28–34)
**Owner: All three**

Tasks (Dev A):
- Complete integration test suite against real PostgreSQL + Redis (testcontainers)
- Load test: `locust` with 20 concurrent users, 30-minute run
- Ensure P95 < 500ms on all read endpoints

Tasks (Dev B):
- E2E tests with Playwright: login → add camera → view stream → view recording
- Mobile-responsive UI check

Tasks (Dev C):
- Docker Compose production configuration (`docker-compose.prod.yml`)
- Gunicorn + uvicorn worker configuration for FastAPI
- Nginx configuration review (HLS delivery, auth_request)
- Full integration test: Matrix SATATYA → MediaMTX → HLS → browser
- Full integration test: Matrix SATATYA motion → Kafka → DB → frontend alert

```
# Gunicorn config for FastAPI (production)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --worker-tmp-dir /dev/shm \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile -
```

Acceptance criteria:
- [ ] `make test` runs full suite in < 5 minutes
- [ ] Coverage ≥ 80% on backend
- [ ] Load test: P95 < 500ms, zero 5xx in 30 minutes
- [ ] Playwright E2E: full user journey completes without errors
- [ ] `docker compose -f docker-compose.prod.yml up --build` — all services healthy
- [ ] Two Matrix SATATYA cameras streaming live simultaneously in browser
- [ ] Motion event from both cameras appears in DB and frontend within 10 seconds

---

## 10. Environment Variables — Complete Reference

```env
# .env.example — copy to .env and fill in all values

# ── Application ──────────────────────────────────
APP_NAME=Sarvanetra
DEBUG=false                             # NEVER true in production
SECRET_KEY=                             # python -c "import secrets; print(secrets.token_hex(32))"
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000

# ── Database ──────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://sarvanetra_user:CHANGE_ME@postgres:5432/sarvanetra
POSTGRES_DB=sarvanetra
POSTGRES_USER=sarvanetra_user
POSTGRES_PASSWORD=                      # generate strong password
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# ── Redis ─────────────────────────────────────────
REDIS_URL=redis://:CHANGE_ME@redis:6379/0
REDIS_PASSWORD=                         # generate strong password

# ── JWT (must match Kong configuration) ──────────
JWT_SECRET_KEY=                         # generate strong secret
JWT_ALGORITHM=HS256
JWT_KEY=cctv@Bsnl                       # Kong consumer key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Kafka ─────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# ── MinIO ─────────────────────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=                       # generate
MINIO_SECRET_KEY=                       # generate
MINIO_RECORDINGS_BUCKET=recordings
MINIO_SNAPSHOTS_BUCKET=snapshots
MINIO_SECURE=false

# ── MediaMTX ──────────────────────────────────────
MEDIAMTX_API_URL=http://mediamtx:9997

# ── Kong ──────────────────────────────────────────
KONG_PG_USER=${POSTGRES_USER}
KONG_PG_PASSWORD=${POSTGRES_PASSWORD}

# ── FCM ───────────────────────────────────────────
FCM_SERVER_KEY=                         # from Firebase Console

# ── Domain ────────────────────────────────────────
DOMAIN_NAME=localhost
HOST_IP=127.0.0.1
```

---

## 11. Makefile — Developer Convenience

```makefile
.PHONY: dev test lint format migrate build clean

dev:
	docker compose up --build

dev-bg:
	docker compose up --build -d

test:
	cd backend && uv run pytest --cov=app --cov-report=term-missing

lint:
	cd backend && uv run ruff check .
	cd backend && uv run mypy app/

format:
	cd backend && uv run ruff format .
	cd frontend && npx prettier --write src/

migrate:
	docker compose exec fastapi alembic upgrade head

makemigrations:
	docker compose exec fastapi alembic revision --autogenerate -m "$(msg)"

logs:
	docker compose logs -f fastapi

shell:
	docker compose exec fastapi python

kafka-ui:
	docker compose --profile debug up kafka-ui

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
```

---

## 12. What NOT to Do — Anti-Patterns from the Existing Codebase

Every item below existed in the old code. None of these patterns are acceptable in the new codebase.

| Anti-pattern | Existing Example | Correct Approach |
|---|---|---|
| `print()` for debugging | `print("test..................", com_id)` | `logger.debug("event", com_id=com_id)` |
| Hardcoded secrets | `secret = 'Bsnl@9876'` in `apiviews.py` | `settings.jwt_secret_key` from `.env` |
| Business logic in router | `views.py` 41KB, 1000+ lines | Service layer with max ~50 lines per method |
| `requests` library (sync) | `requests.get("http://mediamtx:9997/...")` | `httpx.AsyncClient` with `await` |
| `enable_auto_commit=True` | `motion_event_consumer.py` line 29 | `enable_auto_commit=False` + `consumer.commit()` |
| Raw dict responses | `return {"status_code": 200, "data": data}` | Pydantic response models |
| Commented-out code blocks | 50+ lines in `recviews.py` | Delete it. Git history exists. |
| DEBUG = True hardcoded | `settings.py` line 33 | `DEBUG = settings.debug` |
| Duplicate code blocks | `serve_video_segment` in 3 different files | Single service method, multiple routers import it |
| `ThreadPoolExecutor` for I/O | `onvif_motion_producer.py` | `asyncio.create_task()` |
| Bare `except:` clauses | Multiple files | `except SpecificError as exc:` always |
| `time.sleep()` in async context | Would block event loop | `await asyncio.sleep()` |
| Mutable defaults | `def func(items=[])` | `def func(items: list | None = None)` |
| Non-timezone-aware datetimes | `datetime.utcnow()` (deprecated) | `datetime.now(UTC)` |

---

## 13. Progress Tracking

### Phase Completion Checklist

| Phase | Description | Owner | Estimated Days | Status |
|---|---|---|---|---|
| 0 | Project Scaffolding | Dev A | 2 | ⬜ |
| 1 | Database Models & Migrations | Dev A | 3 | ⬜ |
| 2 | FastAPI Core + Auth | Dev A | 4 | ⬜ |
| 3 | Camera & Customer APIs | Dev A + Dev B | 5 | ⬜ |
| 4 | Kong + Stream Tokens | Dev B + Dev C | 4 | ⬜ |
| 5 | Kafka Workers | Dev C | 5 | ⬜ |
| 6 | Recordings & Motion APIs | Dev A + Dev B | 5 | ⬜ |
| 7 | Dashboard & Alerts | Dev B + Dev A | 5 | ⬜ |
| 8 | User Management | Dev B | 3 | ⬜ |
| 9 | Integration Testing & Hardening | All | 7 | ⬜ |

**Total estimated: ~43 working days (~9 weeks) for a team of 3**

### Parallelization Map

```
Week 1:   Dev A: Phase 0 + Phase 1
          Dev B: Next.js setup (running ahead)
          Dev C: Docker Compose + MediaMTX setup

Week 2:   Dev A: Phase 2 (Auth)
          Dev B: Frontend auth + layout shell
          Dev C: ONVIF producer rewrite

Week 3:   Dev A: Phase 3 backend
          Dev B: Phase 3 frontend + Phase 4 frontend
          Dev C: Phase 4 Kong + Phase 5 workers

Week 4-5: Dev A: Phase 5 (workers) + Phase 6 (recordings API)
          Dev B: Phase 6 (recording UI) + Phase 7 (dashboard)
          Dev C: Phase 5 completion + monitoring

Week 6-7: Dev A: Phase 7 backend + Phase 8
          Dev B: Phase 7 frontend + Phase 8
          Dev C: Integration testing infrastructure

Week 8-9: All: Phase 9 (testing + hardening + Matrix SATATYA validation)
```

---

## 14. Version 2 Planning Notes (Future Reference)

When Phase 9 is complete and the system is stable, Version 2 can begin. The following additions require no breaking changes to Version 1 schema.

| V2 Feature | Prerequisite | Complexity |
|---|---|---|
| Keycloak SSO | Existing JWT auth working | High |
| Evidence chain (SHA-256 hash chain on recordings) | `VideoSegment` table stable | Medium |
| Legal holds | Evidence chain complete | Medium |
| Multi-tenant RLS in PostgreSQL | Stable V1 schema | High |
| Kubernetes migration | Docker Compose stable | High |
| React Native mobile app | FastAPI complete | High |
| PTZ camera control | ONVIF producer stable | Medium |

**Schema additions for V2 (non-breaking):**
```sql
-- Add to recordings in a future migration
ALTER TABLE survapp_videosegment ADD COLUMN sha256_hash VARCHAR(64);
ALTER TABLE survapp_videosegment ADD COLUMN on_legal_hold BOOLEAN DEFAULT FALSE;

-- New tables (additive)
CREATE TABLE recording_evidence (...);
CREATE TABLE legal_holds (...);
```

---

## Appendix A — Git Workflow

```
Branch strategy: GitHub Flow
  main          → always deployable, protected
  feature/*     → one branch per Phase (e.g. feature/phase-3-camera-api)
  fix/*         → bug fixes

Commit message format: Conventional Commits
  feat(cameras): add RTSP stream token generation
  fix(motion): resolve race condition in cam_id generation
  test(auth): add integration tests for JWT refresh flow
  refactor(workers): migrate ONVIF producer from threads to asyncio
  docs(api): add endpoint reference for recordings

PR rules:
  - All CI checks must pass (lint, mypy, tests, coverage)
  - At least 1 reviewer approval
  - No direct pushes to main
  - Squash merge preferred
```

## Appendix B — Local Development Quick Start

```bash
# First time setup
git clone <repo>
cd sarvanetra

# Backend
cd backend
pip install uv
uv sync
cp .env.example .env
# Edit .env with your values

# Start infrastructure
cd ..
docker compose up -d postgres redis kafka minio
sleep 10

# Run migrations
cd backend
uv run alembic upgrade head

# Start FastAPI (with hot reload)
uv run uvicorn app.main:app --reload --port 8000

# In another terminal — Start frontend
cd ../frontend
npm install
npm run dev

# In another terminal — Start a worker
cd ../workers/onvif_producer
uv run python main.py
```

## Appendix C — Production Deployment Checklist

Before deploying to Debian VM:

```
Security:
  □ .env file has strong passwords (not defaults)
  □ DEBUG=false in .env
  □ Nginx blocks /docs URL in production
  □ Nginx blocks /internal/* from external traffic
  □ CORS_ALLOWED_ORIGINS is the actual domain, not *
  □ JWT_SECRET_KEY generated with: python -c "import secrets; print(secrets.token_hex(32))"
  □ service-account.json not in git repository
  □ .env not in git repository

Docker:
  □ All images built without cache: docker compose build --no-cache
  □ All services healthy: docker compose ps
  □ No containers running as root (check Dockerfiles)

Verification:
  □ GET /health returns {"status": "ok"}
  □ GET /health/ready returns {"status": "ok", "db": "ok", "redis": "ok"}
  □ Matrix SATATYA cameras streaming HLS in browser
  □ Motion detection events appearing in database
  □ FCM push notification received on test device
```
