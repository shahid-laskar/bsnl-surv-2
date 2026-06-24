# Sarvanetra Codebase: Comprehensive Knowledge Transfer (KT)

Welcome to the **Sarvanetra** project! This document is designed for developers (and AI agents) who are new to the codebase. It provides a top-down view of the architecture, data models, infrastructure, and workflows.

---

## 1. High-Level Architecture

Sarvanetra is a BSNL (Bharat Sanchar Nigam Limited) video surveillance and management platform. It allows users to manage IP cameras, view live streams, review past recordings, and receive motion/health alerts.

The system is highly distributed and relies on several key components:

- **Backend:** FastAPI (Python 3.10+). Handles all business logic, API requests, and database interactions.
- **Frontend:** React + Vite + TypeScript. A modern single-page application (SPA) using React Query for state/data fetching and Tailwind CSS for styling.
- **Database:** PostgreSQL (with `asyncpg` driver and Alembic for migrations).
- **Cache / PubSub:** Redis (used for dashboard caching and temporary state).
- **Message Broker:** Apache Kafka. Decouples the backend REST API from heavy background processing (like ONVIF discovery, motion event consumption, and recording segment processing).
- **Streaming Engine:** MediaMTX. An open-source media server that ingests RTSP streams from cameras and multiplexes them to HLS for frontend consumption.
- **Object Storage:** MinIO. S3-compatible storage used to persist recorded video segments (fmp4).
- **API Gateway:** Kong. Manages JWT authentication and routes traffic.

---

## 2. Infrastructure & Docker Setup

The entire stack is orchestrated via `docker-compose.yml`. Key services include:
- `postgres`, `redis`, `kafka`, `kafka-ui`, `minio` (and a `minio-cleaner` cron).
- `kong` and `kong-migration` for the gateway.
- `mediamtx` and `nginx_hls` for video streaming. Nginx sits in front of MediaMTX to serve HLS segments efficiently and handle auth.
- `fastapi` (backend) and `frontend-app`.
- **Workers:** 
  - `upload-worker`: Monitors Kafka for new recording segments and moves them to MinIO.
  - `status-monitor`: Listens to camera up/down events via Kafka and updates the database.
  - `onvif-producer-1 & 2`: Periodically polls ONVIF-compatible cameras for motion/health.
  - `motion-consumer-1 & 2`: Consumes motion events from Kafka and writes them to PostgreSQL.

---

## 3. Core Domain Models & Hierarchy

The business logic is built around BSNL's geographic and billing hierarchy.

### Geography
- **Circle (`circle_master`)**: The highest level (e.g., Kerala Circle).
- **Business Area (`ba_master`)**: A subdivision within a circle.

### Tenancy
- **Plan (`plan_master`)**: Defines the maximum number of cameras a customer can have.
- **Customer (`customer_master`)**: The tenant (e.g., a bank or office). Belongs to a Circle and BA, and subscribes to a Plan.

### Devices & Cameras
- **Device (`device_master`)**: Edge devices (like NVRs or gateways) that might aggregate cameras.
- **Camera (`camera_master`)**: The physical IP camera. It holds RTSP URLs (`cam_strm1`), credentials (`cam_usrname`, `cam_pass`), and is linked to a customer, circle, and BA.
  - *Crucial note on `cam_id`*: It is generated dynamically at creation (e.g., `CAMKLTVM00001`) using a `SELECT FOR UPDATE` lock in `CameraService._generate_cam_id()` to prevent race conditions.

### Surveillance Data
- **VideoSegment**: Represents a video file (fmp4) in MinIO with start/end timestamps.
- **MotionEvent**: Represents a motion detection window (start to end).
- **Alerts / Health**: `CameraStatusLog` tracks historical up/down events; `CameraHealth` stores the current state.

---

## 4. Authentication & Authorization (RBAC)

The system uses JWT tokens managed jointly by **FastAPI** and **Kong**.

### Token Flow
1. User logs in via `/api/v1/auth/login`.
2. FastAPI verifies credentials and generates an **Access Token** (signed with a secret shared with Kong).
3. The JWT payload includes the user's `role`, `user_id`, and scope (`cir_id`, `ba_id`, `com_id`).
4. Kong verifies the JWT signature on subsequent requests.
5. FastAPI decodes the token in its `get_current_user` dependency to enforce endpoint-level permissions.

### Roles & Scope
- `sysadmin`: Full access across all circles and customers.
- `circle_admin`: Restricted to a specific `cir_id`.
- `ba_admin`: Restricted to a specific `cir_id` and `ba_id`.
- `cust_admin` & `viewer`: Strictly tied to a single `com_id` (Customer).

There is also a short-lived **Stream Token** (15 mins) generated specifically for viewing HLS streams through Nginx.

---

## 5. Backend Code Structure (`/backend/app/`)

- `api/v1/`: FastAPI routers. Each file (e.g., `cameras.py`, `users.py`) maps to a specific domain.
- `core/`: Base configurations, database engine, dependency injection (`dependencies.py`), and security utils.
- `models/`: SQLAlchemy ORM definitions. All models inherit from a common `Base`.
- `schemas/`: Pydantic models for request/response validation.
- `services/`: The "meat" of the backend. Contains business logic (e.g., `CameraService`, `RecordingService`). This keeps the API routers clean.
- `workers/`: Standalone Python scripts that connect to Kafka and process background jobs.

---

## 6. Frontend Code Structure (`/frontend/src/`)

- `components/`: Reusable UI components organized by domain (e.g., `cameras/`, `users/`, `layout/`).
- `pages/`: Top-level route components (e.g., `DashboardPage`, `CamerasPage`).
- `lib/api.ts`: Centralized Axios instances and API endpoint definitions. It maps directly to backend FastAPI routes.
- `types/api.ts`: TypeScript interfaces that **must exactly mirror** the backend Pydantic schemas.
- **State Management**: Uses React Query (`useQuery`, `useMutation`) for caching and data fetching.

---

## 7. Crucial Workflows to Understand

### Adding a Camera
1. User submits the Add Camera form in the Frontend.
2. `CameraService.create()` validates the customer limits.
3. It locks the table, generates the next `cam_id` sequence, and inserts the row.
4. It calls `MediaMTXService.add_path()` to register the new RTSP stream with the MediaMTX streaming server. *(Note: This is currently synchronous and best-effort).*

### Viewing a Live Stream
1. Frontend calls `GET /api/v1/cameras/{cam_id}/stream-token`.
2. Backend generates a 15-minute JWT stream token.
3. Frontend uses a video player (e.g., HLS.js or native) to hit the Nginx HLS proxy with the token in the URL.
4. Nginx validates the token against the backend (`/validate-stream-token`) and serves the `.m3u8` and `.ts`/`.mp4` files generated by MediaMTX.

### Video Recording & Playback
1. MediaMTX continuously records active streams and dumps them to the local disk.
2. The `upload-worker` detects new files, uploads them to MinIO, and sends a Kafka message.
3. The backend consumes this message and creates a `VideoSegment` row in Postgres.
4. When a user requests playback on the timeline, `RecordingService.get_timeline()` queries overlapping segments and motion events, generating presigned MinIO URLs for playback.
