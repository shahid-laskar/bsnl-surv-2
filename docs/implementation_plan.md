# Implementation Plan — Native FastAPI Auth Migration & Django Removal

This plan outlines the steps to fully migrate the authentication system in `bsnl-surv-2` from Django-dependent database structures to a native FastAPI auth flow using Postgres and Kong, as specified in `docs/auth_migration_supplement.md`. This also removes the Django-based project (`surv-shahid`) from the system and updates all database tables to use the `sv_` prefix with standard, clean foreign key naming conventions (e.g. dropping the `_id_id` suffix).

## User Review Required

> [!IMPORTANT]
> - **Schema Migration**: This plan updates the table names to use the `sv_` prefix throughout and renames foreign key columns (e.g. `cir_id_id` to `cir_id`). This is a breaking change for existing database schemas, representing a complete transition away from Django.
> - **Django Removal**: The Django container and code references will be removed from the production setup (`docker-compose.prod.yml`). The FastAPI backend will serve as the sole REST API backend.
> - **Kong Config Update**: Kong admin URL and settings are integrated into `Settings` and `.env` configurations.

## Proposed Changes

### Configuration Updates

#### [MODIFY] [config.py](file:///opt/bsnl-surv-2/backend/app/core/config.py)
- Add `kong_admin_url: str` to `Settings`.
- Add `jwt_refresh_token_expire_days: int = 30` to `Settings`.

#### [MODIFY] [.env.example](file:///opt/bsnl-surv-2/backend/.env.example) and [main .env.example](file:///opt/bsnl-surv-2/.env.example)
- Add variables `KONG_ADMIN_URL`, `INITIAL_ADMIN_PASSWORD`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, etc., as specified in section 18 of the supplement.

---

### Database & Models

#### [MODIFY] [0001_initial_schema.py](file:///opt/bsnl-surv-2/backend/alembic/versions/0001_initial_schema.py)
- Rewrite the migration to create the clean database tables with the `sv_` prefix, correct columns, foreign keys without the double `_id_id` suffix, and no Django table dependencies.
- Add initial seed data (circles, BAs, plans, streams, and the initial `admin` sysadmin user with password hashed via passlib bcrypt) at the end of the migration.

#### [MODIFY] [geography.py](file:///opt/bsnl-surv-2/backend/app/models/geography.py)
- Rename tables to `sv_circle_master` and `sv_ba_master`.
- Change `ba_master.cir_id_id` to `ba_master.cir_id`.

#### [MODIFY] [customer.py](file:///opt/bsnl-surv-2/backend/app/models/customer.py)
- Rename tables to `sv_plan_master` and `sv_customer_master`.
- Change foreign keys from `_id_id` suffix to single `_id` suffix (`cir_id`, `ba_id`, `plan_id`).

#### [MODIFY] [device.py](file:///opt/bsnl-surv-2/backend/app/models/device.py)
- Rename tables to `sv_stream_master` and `sv_device_master`.

#### [MODIFY] [camera.py](file:///opt/bsnl-surv-2/backend/app/models/camera.py)
- Rename table `sv_camera_master` (kept).
- Change foreign keys from `_id_id` suffix to single `_id` suffix (`cir_id`, `ba_id`, `com_id`, `device_id`, `added_by`, `strm_type_id`).
- Reference `added_by` to the new `sv_users.id` table instead of `auth_user.id`.

#### [MODIFY] [recording.py](file:///opt/bsnl-surv-2/backend/app/models/recording.py)
- Rename table to `sv_video_segment`.
- Ensure `camera_id` references `sv_camera_master.id`.

#### [MODIFY] [motion.py](file:///opt/bsnl-surv-2/backend/app/models/motion.py)
- Rename tables to `sv_motion_event` and `sv_motion_detection_health`.
- Align back-populates relation names with `camera_master`.

#### [MODIFY] [alert.py](file:///opt/bsnl-surv-2/backend/app/models/alert.py)
- Rename tables to `sv_camera_status_log` and `sv_camera_health`.

#### [MODIFY] [audit.py](file:///opt/bsnl-surv-2/backend/app/models/audit.py)
- Rename tables to `sv_api_log` and `sv_container_stats`.

#### [NEW] [auth.py](file:///opt/bsnl-surv-2/backend/app/models/auth.py)
- Define `SvUser` (table `sv_users`), `SvKongConsumer` (table `sv_kong_consumers`), and `SvRefreshToken` (table `sv_refresh_tokens`) SQLAlchemy models, replacing `app/models/user.py`.

#### [DELETE] [user.py](file:///opt/bsnl-surv-2/backend/app/models/user.py)
- Remove `user.py` as it's replaced by `auth.py`.

#### [MODIFY] [__init__.py](file:///opt/bsnl-surv-2/backend/app/models/__init__.py)
- Update imports to use `SvUser`, `SvKongConsumer`, and `SvRefreshToken`.

---

### Core Security & Dependencies

#### [MODIFY] [security.py](file:///opt/bsnl-surv-2/backend/app/core/security.py)
- Implement `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `create_refresh_token`, `hash_refresh_token`, `create_stream_token`, `decode_stream_token` according to Section 9 of the supplement.
- Use `jose` package to preserve compatibility without adding dependency overhead.

#### [MODIFY] [dependencies.py](file:///opt/bsnl-surv-2/backend/app/core/dependencies.py)
- Update `get_current_user` to decode the token using `decode_access_token`, fetch `SvUser` from database, and validate `is_active`.
- Update `require_role` to support `is_superuser` bypass and enforce the correct role checks.
- Add `get_scoped_com_id` utility.

---

### Services & API Routers

#### [NEW] [kong_service.py](file:///opt/bsnl-surv-2/backend/app/services/kong_service.py)
- Create `KongService` using `httpx` to register and deregister consumer/credential objects on Kong Admin API.

#### [MODIFY] [auth_service.py](file:///opt/bsnl-surv-2/backend/app/services/auth_service.py)
- Implement login with bcrypt validation against `SvUser`, and generate access/refresh tokens.
- Implement token refresh rotation (opaque token lookup in database, revoke/rotate).
- Implement helper methods: `change_password`, `revoke_refresh_token`, and `register_device_token`.

#### [NEW] [user_service.py](file:///opt/bsnl-surv-2/backend/app/services/user_service.py)
- Implement `UserService` managing creating, updating, and deactivating users, integrating `KongService` for consumer provisioning.

#### [MODIFY] [auth.py](file:///opt/bsnl-surv-2/backend/app/api/v1/auth.py)
- Update login, refresh, logout, me, change-password, and device-token routers to match Pydantic schemas and invoke `AuthService`.
- Keep `validate-stream-token` endpoint intact.

#### [NEW] [users.py](file:///opt/bsnl-surv-2/backend/app/api/v1/users.py)
- Create user endpoints for CRUD operations (creating, deactivating, updating users) scoped by roles.

#### [MODIFY] [__init__.py](file:///opt/bsnl-surv-2/backend/app/api/v1/__init__.py)
- Register `users_router` under `/api/v1`.

#### [MODIFY] [cameras.py](file:///opt/bsnl-surv-2/backend/app/api/v1/cameras.py)
- Update query filters, scope assertion checks, and payload attributes to use single `_id` suffix attributes.

#### [MODIFY] [dashboard.py](file:///opt/bsnl-surv-2/backend/app/api/v1/dashboard.py)
- Update queries to use single `_id` suffix columns.

#### [MODIFY] [camera_service.py](file:///opt/bsnl-surv-2/backend/app/services/camera_service.py)
- Update column references on `camera_master` and `customer_master` models.

---

### Docker & Infrastructure

#### [MODIFY] [docker-compose.prod.yml](file:///opt/bsnl-surv-2/docker-compose.prod.yml)
- Remove `django` service entirely.
- Remove `nginx`'s dependency on `django`.
- Ensure Kong is configured with `JWT_SECRET_KEY` and the correct environment variables.

---

### Unit & Integration Tests

#### [NEW] [test_security.py](file:///opt/bsnl-surv-2/backend/tests/unit/test_security.py)
- Add unit tests for password hashing/verification and JWT encoding/decoding.

#### [NEW] [test_auth_api.py](file:///opt/bsnl-surv-2/backend/tests/integration/test_auth_api.py)
- Add integration tests for login, refresh token rotation, me profile, and logout.

---

## Verification Plan

### Automated Tests
- Run `pytest` to run all unit and integration tests:
  ```bash
  cd backend && uv run pytest
  ```
- Run static checks to ensure type safety and code quality:
  ```bash
  cd backend && uv run ruff check .
  cd backend && uv run mypy app
  ```

### Manual Verification
- Spin up the database container:
  ```bash
  docker compose up -d postgres redis kafka minio mediamtx
  ```
- Run Alembic migrations:
  ```bash
  cd backend && uv run alembic upgrade head
  ```
- Verify the seed admin user is inserted correctly.
