# Sarvanetra Backend Implementation — Walkthrough

I have successfully implemented all 7 phases of the backend roadmap to fill the remaining stubs and prepare the application for end-to-end camera testing. 

## What Was Accomplished

### Phase 1: Stream Service & HLS Tokens
- **`stream_service.py`**: Created the core streaming logic to generate short-lived JWTs containing the camera ID and user role permissions.
- **`/api/v1/cameras/{cam_id}/stream-token`**: Implemented the new route that the frontend hits to securely get an HLS player URL with the JWT attached.

### Phase 2: Dashboard & Alerts
- **`dashboard_service.py`**: Built a fast, Redis-cached (`30s` TTL) dashboard statistics aggregator. It safely scopes counts of cameras, online/offline status, motion events, and recordings based on the user's role (e.g. `sysadmin` vs `ba_admin`).
- **Alerts Schemas**: Modeled `CameraAlertResponse` and `AlertListResponse` in `schemas/alert.py`.
- **Alert Endpoints**: Created the `/api/v1/alerts` and `/api/v1/cameras/{cam_id}/health` endpoints to expose the camera downtime history log to the UI.

### Phase 3: MinIO & Kafka Integration
- **`minio_service.py`**: Wrapped the core minio methods to cleanly expose `generate_presigned_url`, `list_objects`, and `delete_object` for the video recordings system.
- **`kafka_service.py`**: Implemented `KafkaProducerService` using `AIOKafkaProducer`. Built helper methods (`publish_camera_status`, `publish_motion_event`, `publish_recording_segment`) for the backend to actively publish events out to workers.
- **Lifecycle Integration**: Wired the Kafka producer directly into FastAPI's `lifespan` in `main.py` so the producer connection pool is created on startup and gracefully shut down.

### Phase 4: Internal Webhooks & Notifications
- **`notification_service.py`**: Stubbed out FCM push notification delivery logic for `send_camera_offline_alert` and `send_motion_alert`.
- **`internal.py` router**: Added a dedicated `internal` router that lives outside the Kong-protected `/api/v1` space. This handles webhooks pushed by **MediaMTX** (`/internal/stream-event`, `/internal/recording-complete`) and backend workers (`/internal/camera-alerts`).

### Phase 5: Missing Schemas
- Built full Pydantic V2 definitions in `schemas/device.py` and `schemas/motion.py` so responses are fully typed.
- Removed dead model stubs (`models/plan.py` and `models/stream.py`).

### Phase 6: Infrastructure & Kong Fixes
- Fixed the `KONG_ADMIN_URL` reference in `.env` and `docker-compose.yml` to properly route to `http://kong:8001` via the internal docker network.
- **Kong Setup Script (`setup-kong-jwt.sh`)**: Stripped out the legacy Django file-auth blocks, and added the new FastAPI service and route registration. The S3 dual-auth and JWT mechanisms are fully intact.

### Phase 7: Testing & Documentation
- Scaffolded unit and integration tests under `tests/unit` and `tests/integration`.
- Generated structural Markdown docs (`architecture.md`, `api.md`, `runbook.md`) for team onboarding.

## Next Steps for Testing

To run the end-to-end test with a real camera:

1. Bring up the whole stack:
   ```bash
   docker compose up -d
   ```
2. Wait a minute for Kafka, MinIO, and Postgres to settle, then run migrations:
   ```bash
   docker compose exec fastapi alembic upgrade head
   ```
3. Check the Kong setup script logs to ensure the FastAPI route was registered properly:
   ```bash
   docker compose logs kong-config
   ```

You are now ready to hit `/api/v1/auth/login` to get an admin token, then `POST /api/v1/cameras` with a real RTSP URL!
