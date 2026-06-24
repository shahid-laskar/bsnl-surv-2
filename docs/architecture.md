# Sarvanetra: End-to-End Issues & Phase-Wise Implementation Plan

This document outlines the current technical debt, missing features, and end-to-end issues present in the Sarvanetra codebase, followed by a structured, phase-wise implementation plan for AI agents to continue development.

---

## Part 1: Current End-to-End Issues

### 1. Security: Camera Credentials in Plaintext
**Issue:** In `camera_master` (`app/models/camera.py`), `cam_pass` is stored as a plaintext string.
**Impact:** Severe security vulnerability. If the database is compromised, all camera credentials are exposed.
**Requirement:** Implement symmetric encryption (e.g., using `cryptography.fernet`) for `cam_pass` at rest. Decrypt only in memory when registering streams with MediaMTX or connecting via ONVIF.

### 2. Synchronization: MediaMTX Path Registration
**Issue:** When a camera is created or updated in `CameraService.create()` / `CameraService.update()`, the registration with MediaMTX (`_mtx.add_path()`) happens synchronously via REST API. It is "best-effort."
**Impact:** If MediaMTX is temporarily unreachable, the database transaction succeeds, but the stream is never configured. The system state becomes inconsistent.
**Requirement:** Decouple this using Kafka. `CameraService` should publish a `camera_configured` event. A dedicated worker should reliably consume this event with retries to configure MediaMTX.

### 3. Deactivation Cascade: Zombie Workers
**Issue:** `CameraService.deactivate()` soft-deletes a camera (`is_active = False`) and removes the MediaMTX path. However, the `onvif_producer` workers are not proactively notified to drop the camera from their polling loops.
**Impact:** Workers waste resources polling deactivated cameras, potentially filling logs with connection errors.
**Requirement:** Broadcast deactivation events via Kafka so `onvif_producer` processes can dynamically reload their active camera lists without a full restart.

### 4. API Consistency: Pagination Patterns
**Issue:** Some list endpoints return standard `PaginatedResponse` (`cameras`, `customers`), others return flat lists (`devices`), and others return a unique `{ items, total }` without pagination metadata (`alerts`).
**Impact:** Frontend developers must write custom, boilerplate code for each table/list view instead of relying on a single generic hook.
**Requirement:** Standardize all list endpoints to use the exact same `PaginatedResponse` schema and query parameters (`page`, `page_size`, or cursor-based).

### 5. Worker Scalability: Hardcoded ONVIF Producers
**Issue:** In `docker-compose.yml`, `onvif-producer-1` and `onvif-producer-2` are hardcoded with specific hostnames and environment variables. They split cameras blindly.
**Impact:** Does not scale dynamically. If one worker crashes, its portion of cameras is not polled.
**Requirement:** Implement dynamic partitioning. Use Kafka Consumer Groups or a Redis-based distributed lock/lease system so workers can dynamically claim healthy cameras and balance the load.

### 6. Frontend Validation: Granular Error Handling
**Issue:** Modals (like `AddCustomerModal` and `AddUserModal`) catch errors via React Query and display a generic message or the raw string.
**Impact:** If the FastAPI backend returns a `422 Unprocessable Entity` with specific field errors (e.g., "Invalid GSTN format"), the user doesn't see which field failed.
**Requirement:** Map FastAPI's `detail` array in 422 responses to React Hook Form or custom state errors on specific input fields.

---

## Part 2: Phase-Wise Implementation Plan

AI Agents should tackle these issues systematically using the following phases.

### Phase 1: Security & Core Stability
*Focus: Address critical security vulnerabilities and ensure data consistency.*

- **Task 1.1: Encrypt Camera Credentials**
  - Add a `FERNET_KEY` to `config.py` and `.env`.
  - Update `camera_master` model setters/getters or handle encryption in `CameraService` before DB inserts/updates.
  - Write an Alembic migration script to iterate over existing plaintext passwords, encrypt them, and save them back.
- **Task 1.2: Standardize API Pagination**
  - Update `alertApi.list` and `deviceApi.list` in the backend to return `PaginatedResponse`.
  - Update corresponding frontend hooks and TypeScript types in `src/types/api.ts` to match the standard.

### Phase 2: Asynchronous Workflows & Consistency
*Focus: Remove brittle synchronous calls and rely on Kafka.*

- **Task 2.1: Asynchronous MediaMTX Configuration**
  - Remove synchronous `_mtx.add_path()` calls from `CameraService`.
  - Introduce `kafka_service.publish_camera_config_change(cam_id)`.
  - Create a new Python worker (`mediamtx_config_worker.py`) that listens to these events, attempts to register the path with MediaMTX, and retries on failure (using exponential backoff).
- **Task 2.2: Kafka-Driven Camera Deactivation**
  - Update `CameraService.deactivate()` and `reactivate()` to publish Kafka events.
  - Update `onvif_producer.py` to listen to these events on a separate async thread, allowing it to instantly add or drop cameras from its polling loop.

### Phase 3: Worker Scalability
*Focus: Make background processing resilient and horizontally scalable.*

- **Task 3.1: Distributed Camera Polling**
  - Refactor `onvif_producer.py`. Instead of reading a static slice of the database, implement a Redis-based lease mechanism.
  - Each worker acquires a 60-second lock/lease on a camera. If a worker dies, the lock expires, and another worker picks it up.
  - Remove hardcoded `worker-1` and `worker-2` from `docker-compose.yml`; allow simple `docker compose scale onvif_producer=5`.

### Phase 4: Frontend Polish & UX
*Focus: Improve error reporting and user feedback.*

- **Task 4.1: API Error Interceptor**
  - Create an Axios interceptor in `src/lib/api.ts` that detects `422` status codes.
  - Parse the `detail` array from FastAPI and format it into a standardized `{ field: "message" }` object.
- **Task 4.2: Field-Level Form Errors**
  - Refactor `AddCustomerModal` and `AddUserModal` to consume the structured error object and display red validation text directly beneath the offending input fields (e.g., beneath the GSTN or Email inputs).

### Phase 5: End-to-End Testing Pipeline
*Focus: Ensure future changes don't break existing workflows.*

- **Task 5.1: API Integration Tests**
  - Implement `pytest` fixtures for an async test database.
  - Write tests for the full user creation and camera creation flows.
- **Task 5.2: Stream/Worker Mocking**
  - Write tests verifying that `CameraService` correctly publishes Kafka messages, mocking the actual Kafka broker.


