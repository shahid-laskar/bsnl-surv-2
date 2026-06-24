# Sarvanetra Backend API Reference
### For an AI agent completing frontend integration work

---

## How to use this document

This is the **actual, verified behavior of the FastAPI backend** — derived directly from
reading `app/api/v1/*.py`, `app/schemas/*.py`, `app/models/*.py`, and `app/services/*.py`,
not from the original planning documents. Where the planning docs
(`sarvanetra_implementation_plan.md`, `auth_migration_supplement.md`) describe a different
endpoint shape or path than what's actually implemented, **this document reflects what's
actually implemented** — treat the planning docs as historical context only.

The frontend's `src/lib/api.ts` and `src/types/api.ts` appear to have been written against
the *planned* API surface rather than the implemented one. Section 4 below ("Frontend
Integration Gaps") is a line-by-line diff of every place those two disagree. **Start there**
— it's the actionable backlog. Sections 1–3 are reference material to consult while fixing
items in Section 4.

A handful of backend-side bugs were also found while compiling this (Section 3). Some of the
frontend gaps in Section 4 can't be fixed purely on the frontend because the backend endpoint
they'd call is either broken, missing, or shadowed by a duplicate route. Those are marked
**[BACKEND FIX REQUIRED]**.

---

## 1. Conventions

**Base path:** all endpoints below are relative to `/api/v1` unless noted "internal" (those
are mounted at `/internal`, blocked from external traffic by Nginx, no auth).

**Auth:** `Authorization: Bearer <JWT>`. Obtained from `POST /auth/login`. The token's `iss`
claim is per-user (`sarvanetra_user_{id}`), not a fixed value — this is what Kong's JWT
plugin validates in front of FastAPI. FastAPI re-validates `exp` and re-fetches the user from
DB on every request (so a deactivated user is rejected on their very next call, not just at
next login).

**Roles:** `sysadmin` > `circle_admin` > `ba_admin` > `cust_admin` > `viewer`. A user with
`is_superuser=true` bypasses all role checks regardless of `role`. Scoping (which rows a role
can see/touch) is enforced in the **service layer**, not the router — e.g. `circle_admin` is
restricted to their own `cir_id`, not by a route-level dependency.

**Standard pagination wrapper** (`PaginatedResponse<T>` in TS, used by *most* but not all
list endpoints — see Section 4 for the ones that don't actually use it despite the frontend
assuming they do):
```json
{ "items": [...], "total": 0, "page": 1, "page_size": 25, "pages": 0 }
```

**Standard error shape** (from the global exception handler, `app/core/middleware.py`):
```json
{ "error": { "code": "CAMERA_NOT_FOUND", "message": "Camera 'X' not found" } }
```
Pydantic validation errors (422) use the same envelope with an extra `details` array of
field-level errors.

**Swagger UI caveat:** the `/api/docs` Authorize button renders a full OAuth2 password-grant
dialog (client_id/client_secret) because `app/core/dependencies.py` uses
`OAuth2PasswordBearer`. That flow POSTs form-encoded data to `tokenUrl`, but
`POST /auth/login` only accepts JSON — so the Authorize button will 422. Use "Try it out" on
the login endpoint directly, copy `access_token`, and paste it manually as a header on other
requests instead.

---

## 2. Endpoint Reference

### Auth — `app/api/v1/auth.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/login` | none | JSON body, not form data |
| POST | `/auth/refresh` | none | rotates refresh token (single-use) |
| GET | `/auth/me` | any user | |
| POST | `/auth/change-password` | any user | 204 |
| POST | `/auth/logout` | none | revokes the given refresh token; access token stays valid until natural expiry (stateless JWT) |
| POST | `/auth/device-token` | any user | registers FCM/APNs token, 204 |
| POST | `/auth/validate-stream-token?token=` | none | internal use by Nginx `auth_request`, not for frontend |

```ts
// POST /auth/login
Request:  { username: string; password: string; device_id?: string }
Response: { access_token: string; refresh_token: string; token_type: "bearer";
            expires_in: number; user: UserInResponse }

// UserInResponse
{ id, username, email, first_name, last_name, role,
  com_id: number|null, cir_id: number|null, ba_id: number|null,
  is_active: boolean, date_joined: string }
```

---

### Users — `app/api/v1/users.py`, prefix `/users`

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/users/` | sysadmin, circle_admin, ba_admin, cust_admin | trailing slash matters |
| PUT | `/users/{user_id}` | any user (self-update has extra restrictions — see below) | |
| DELETE | `/users/{user_id}` | sysadmin, circle_admin, ba_admin, cust_admin | soft-delete, 204 |
| GET | `/users/` | any user | scoped by role server-side |
| GET | `/users/{user_id}` | any user | 403 if outside requester's scope |

Self-update restrictions (`UserService._validate_update_permission`): a user updating their
**own** record cannot change their own `role`, `is_active`, `cir_id`, `ba_id`, or `com_id` —
those fields are silently rejected with 403 even though the route itself has no extra role
guard.

---

### Cameras — `app/api/v1/cameras.py`, prefix `/cameras`

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/cameras` | any user | **`com_id` query param is required**, not optional |
| POST | `/cameras` | sysadmin, circle_admin | |
| GET | `/cameras/{cam_id}` | any user | scoped to own `com_id` unless sysadmin/circle_admin/ba_admin |
| PATCH | `/cameras/{cam_id}` | sysadmin, circle_admin | |
| POST | `/cameras/{cam_id}/deactivate` | sysadmin, circle_admin | soft delete, removes MediaMTX path |
| POST | `/cameras/{cam_id}/reactivate` | sysadmin, circle_admin | re-registers MediaMTX path |
| GET | `/cameras/{cam_id}/stream-token` | any user | **[BACKEND FIX REQUIRED]** — see Section 3, bug #1 |
| GET | `/cameras/{cam_id}/status` | any user | live MediaMTX readiness check, untyped dict response |

```ts
// GET /cameras?com_id=&is_active=&page=&page_size=
Response: PaginatedResponse<CameraListItem>
CameraListItem: { cam_id: string|null, cam_name, cam_loc, is_active, motion_active, com_id }

// POST /cameras
Request (CameraCreateRequest):
{
  cam_name: string; cam_loc: string; cam_make: string;
  cam_usrname: string; cam_pass: string;
  cam_strm1: string;          // must start with rtsp://, rtmp://, OR be literally "publisher"
  cam_strm2?: string; cam_strm3?: string;
  cam_onvif?: number;
  motion_active?: boolean;     // default false
  com_id: number; device_id: number;
  strm_type_id?: number;       // OPTIONAL on backend — frontend's TS type wrongly marks it required, see Section 4
}
Response: CameraResponse
{ id, cam_id: string|null, cam_name, cam_loc, cam_make, cam_usrname,
  // cam_pass intentionally never returned
  cam_strm1, cam_strm2: string|null, cam_strm3: string|null, cam_onvif: number|null,
  is_active, motion_active, upd_time: string,
  com_id, cir_id, ba_id, device_id, strm_type_id: number|null }

// GET /cameras/{cam_id}/status — no response_model, raw dict
{ cam_id: string, ready: boolean, readers: number, source?: string }
```

`cam_id` itself is server-generated, format `CAM{circle_code}{ba_code}{00001}` (e.g.
`CAMKRTVM00001`), via `CameraService._generate_cam_id` using `SELECT ... FOR UPDATE` to avoid
race conditions — never send it in the create request.

---

### Alerts & Camera Health — `app/api/v1/alerts.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/alerts?skip=&limit=` | any user | **does NOT use `PaginatedResponse`** — see below |
| PATCH | `/alerts/{alert_id}/acknowledge` | any user | scoped by role |
| GET | `/cameras/{cam_id}/health` | any user | **this is the version that actually wins** — see Section 3, bug #2 |

```ts
// GET /alerts — note the shape difference from every other list endpoint
Response: { items: CameraAlertResponse[]; total: number }   // NO page/page_size/pages fields
CameraAlertResponse: { id, camera_id, cam_name: string|null, status: "up"|"down",
                       timestamp: string, duration: string|null, acknowledged: boolean }

// GET /cameras/{cam_id}/health
Response: CameraHealthResponse
{ current_status: "up"|"down", last_change: string, last_downtime_duration: string|null }
```

---

### Customers — `app/api/v1/customers.py`, prefix `/customers`; Plans at `/plans`

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/customers?ba_id=&page=&page_size=` | any user | returns the **minimal** `CustomerListItem` shape — see Section 4 |
| POST | `/customers` | sysadmin, circle_admin, ba_admin | `cir_id`/`ba_id` immutable after creation |
| GET | `/customers/{id}` | any user | returns the **minimal** `CustomerResponse` shape — see Section 4 |
| PATCH | `/customers/{id}` | sysadmin, circle_admin, ba_admin | |
| GET | `/plans` | any user | reference data |

```ts
// What the backend ACTUALLY returns (not what CustomersPage.tsx expects — see Section 4):
CustomerListItem: { id, com_name, cir_id, ba_id, plan_id }
CustomerResponse:  { id, com_name, com_adr, gstn: string|null, cir_id, ba_id, plan_id }
PlanResponse:      { id, plan_name, cam_limit }
```

Note there is **no** `cir_name`, `ba_name`, `plan_name`, `camera_count`, or `camera_limit` on
either shape. These would require joins/aggregates the service layer doesn't currently do.

---

### Geography — `app/api/v1/geography.py`, no router prefix (paths are literal)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/circles` | any user | |
| POST | `/circles` | sysadmin | |
| GET | `/circles/{cir_id}/bas` | any user | plain array, not paginated |
| POST | `/circles/{cir_id}/bas` | sysadmin | |
| GET | `/bas/{ba_id}/customers` | any user | plain array of `CustomerListItem` (minimal shape, same gap as above) |

```ts
CircleResponse: { id, cir_name, cir_code }
BAResponse:     { id, ba_name, ba_code, cir_id }
```

No frontend UI currently exists to call the two POST endpoints (circle/BA creation) — these
are sysadmin-only setup operations, currently only reachable via raw API calls.

---

### Devices — `app/api/v1/devices.py`, prefix `/devices`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/devices?staging_status=` | any user | **flat array**, capped at 200 server-side via `.limit(200)`, no pagination params accepted at all |
| POST | `/devices/capture` | **none** (FastAPI-level) | upserts by `device_no`; MQTT-announce endpoint |
| POST | `/devices/status` | **none** (FastAPI-level) | heartbeat from MQTT bridge |
| GET | `/devices/stream-types` | any user | reference data for the stream-type dropdown |

```ts
DeviceResponse: { id, device_id, staging_status: string|null, status_log: string|null,
                  dev_name: string|null, dev_loc: string|null,
                  mqtt_status: string|null, mqtt_update: string|null }
StreamTypeResponse: { id, strm_type: string, remark: string|null }
```

**No `GET /devices/{id}` exists.** "No FastAPI-level auth" doesn't mean publicly reachable —
Kong's JWT plugin sits in front of the entire `/api` path per `setup-kong-jwt.sh`, so a valid
JWT is still required to reach these through the real deployment; FastAPI just doesn't do an
*additional* role check on top of that.

---

### Recordings — `app/api/v1/recordings.py`, prefix `/recordings`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/recordings/timeline/{cam_id}?start=&end=&include_motion=` | any user | **this is the only way to query segments** — there is no flat list endpoint |
| GET | `/recordings/{segment_id}/video` | any user | streams from MinIO, HTTP Range supported |
| GET | `/recordings/{segment_id}/presigned-url?expires=` | any user | returns `{ url, expires_in }` |
| POST | `/recordings/segments` | none (internal, called by `upload_worker`) | |

```ts
// GET /recordings/timeline/{cam_id} — start & end are REQUIRED, ISO datetime
Response: TimelineResponse
{ cam_id, camera_name, segments: TimelineSegmentData[], total_duration, segment_count,
  start_date, end_date }

TimelineSegmentData:
{ id, start_time: number, end_time: number, duration: number,
  cumulative_start: number, cumulative_end: number,
  url: string,        // already-built path to GET /recordings/{id}/video
  file_path, readable_start, readable_end,
  motion_events: MotionEventData[], motion_count: number }
```

**There is no merge or zip-download endpoint implemented**, despite
`app/schemas/recording.py` defining `MergeSegmentsRequest`/`DownloadZipRequest` for exactly
this purpose. The schemas exist; the router functions that would use them don't.

---

### Motion — `app/api/v1/motion.py`, no router prefix (paths are literal)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/cameras/{cam_id}/motion?start=&end=&is_active=&page=&page_size=` | any user | the only motion-list endpoint that exists |
| POST | `/camera-alerts` | none | ingests `{ camera, status: "ready"\|"notReady", timestamp }` — distinct from `/internal/camera-alerts`, see note below |
| GET | `/cameras/{cam_id}/health` | any user | **dead code** — shadowed by `alerts.py`'s version of the same path; never actually executes (see Section 3, bug #2) |

```ts
Response: PaginatedResponse<MotionEventResponse>
MotionEventResponse: { id, camera_id, motion_start, motion_end: string|null,
                       is_active, duration_seconds: number|null }
```

`app/schemas/motion.py` defines its own `MotionEventResponse`/`MotionHealthResponse` classes
with slightly different fields (e.g. includes `cam_name`) — those are **not** what this
endpoint actually returns. The router defines and uses its own local Pydantic models instead;
`schemas/motion.py`'s versions appear to be unused dead code.

There are two separate camera-status-ingest endpoints with similar purposes but different
contracts — don't conflate them:
- `POST /api/v1/camera-alerts` (this file) — `{camera, status: "ready"|"notReady", timestamp}`, writes `CameraStatusLog` + updates `CameraHealth`. Called by the `status_monitor` Kafka worker.
- `POST /internal/camera-alerts` (`internal.py`) — `{cam_id, status, reason?}`, writes `CameraStatusLog` and triggers a push notification on `status == "down"`.

---

### Streams — `app/api/v1/streams.py`, prefix `/cameras`

**[BACKEND FIX REQUIRED]** — this entire router's one endpoint
(`GET /cameras/{cam_id}/stream-token`) is currently unreachable dead code. See Section 3,
bug #1. Its implementation (`StreamService.generate_stream_token`) is correct; it's just
never invoked because `cameras.py` registers the identical path first. Don't write frontend
code against this file's behavior — the request will actually be served by `cameras.py`'s
broken version.

---

### Dashboard — `app/api/v1/dashboard.py`, prefix `/dashboard`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/dashboard/stats` | any user | Redis-cached 30s, per role+com_id |
| GET | `/dashboard/camera-status` | any user | Redis-cached 30s |

```ts
// GET /dashboard/stats — untyped dict, but DashboardService always returns exactly:
{ total_cameras: number, online_cameras: number, offline_cameras: number,
  active_motion_events: number, total_recordings: number, total_customers: number }

// GET /dashboard/camera-status — untyped list of dicts:
[{ cam_id: string, cam_name: string, status: "up" | "down" }]
```

---

### Health — `app/api/v1/health.py`, no auth, no `/api/v1` business logic dependency

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness — always 200 if process is up |
| GET | `/health/ready` | readiness — 503 if DB or Redis unreachable |

---

### Internal — `app/api/v1/internal.py`, mounted at `/internal` directly in `main.py`, not under `/api/v1`

Not relevant to frontend work — these are webhook targets for MediaMTX and Kafka workers,
blocked from external traffic by Nginx. Listed here only so the agent doesn't confuse them
with the similarly-named `/api/v1/camera-alerts` endpoint in `motion.py` (see note above).

---

## 3. Backend Bugs Found While Compiling This Reference

These aren't frontend problems, but they block frontend features from ever working correctly
no matter how the frontend code is written — flagging them so the agent doesn't waste time
debugging frontend code that's actually fine.

### Bug #1 — duplicate route, `GET /cameras/{cam_id}/stream-token` is broken

Both `app/api/v1/cameras.py` and `app/api/v1/streams.py` register the identical path
`GET /cameras/{cam_id}/stream-token`. `app/api/v1/__init__.py` includes `cameras_router`
before `streams_router`, so FastAPI always matches `cameras.py`'s version; `streams.py`'s
correctly-implemented version never runs.

`cameras.py`'s version is itself broken — it builds the response as:
```python
return StreamTokenResponse(
    cam_id=cam_id, stream_url=stream_url, token=token,
    expires_in=settings.jwt_stream_token_expire_minutes * 60,   # <- wrong field name
)
```
but `StreamTokenResponse` (`app/schemas/camera.py`) requires `expires_at: datetime`, not
`expires_in`. This will raise a Pydantic `ValidationError` → unhandled exception → 500, every
single time this endpoint is called.

**Fix:** delete the duplicate endpoint in `cameras.py` (lines defining `get_stream_token`),
and rely solely on `streams.py`'s version, which already builds the response correctly via
`StreamService.generate_stream_token`.

### Bug #2 — duplicate route, `GET /cameras/{cam_id}/health`

Both `app/api/v1/alerts.py` (mounted as `camera_health_router`) and `app/api/v1/motion.py`
(part of `motion_router`) register `GET /cameras/{cam_id}/health`. Registration order in
`__init__.py` puts `camera_health_router` first, so `alerts.py`'s version always wins;
`motion.py`'s version is dead code.

This one isn't broken (alerts.py's version works correctly), but it's worth removing the
dead duplicate in `motion.py` to avoid confusion — its response shape differs slightly (it
returns a raw dict with `last_downtime_duration_seconds: number`, vs. the real, executing
version's `CameraHealthResponse` with `last_downtime_duration: string`). Anyone reading
`motion.py` in isolation would reasonably but incorrectly assume that's what the endpoint
returns.

### Bug #3 — `CustomerResponse`/`CustomerListItem` missing fields the frontend already expects

Covered in Section 4 below, but worth restating as a backend gap: the frontend's `Customer`
TS type and `CustomersPage.tsx` were built expecting `cir_name`, `ba_name`, `plan_name`,
`camera_count`, and `camera_limit` on every customer object. None of these exist on the
backend's response models. This needs a backend fix (extending `CustomerService` queries
with joins to `circle_master`/`ba_master`/`plan_master` and a count subquery against
`camera_master`), not a frontend one — the data simply isn't available from the API as it
stands.

---

## 4. Frontend Integration Gaps (`src/lib/api.ts` vs. reality)

Each entry: what the frontend currently calls → what actually exists on the backend → fix
direction.

### `deviceApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `list()` typed `→ PaginatedResponse<Device>`, accepts `page`/`page_size` | Returns flat `Device[]`, ignores `page`/`page_size` entirely | Change return type to `Device[]`; drop the unused params or leave them (harmless no-ops) |
| `streamTypes()` | **Doesn't exist in api.ts at all** | Add: `streamTypes: () => api.get<StreamTypeMaster[]>("/api/v1/devices/stream-types")` — name it `StreamTypeMaster`, not `StreamType` (that name's taken by the existing `"RTSP"\|"RTMP"\|"RTSP CLOUD"` union in `types/api.ts`) |
| `get(id)` → `GET /api/v1/devices/${id}` | **No such backend endpoint exists** | Either remove this method (if unused) or add the backend endpoint if a device-detail page is planned |
| `updateHeartbeat(deviceId, timestamp)` → `POST /api/v1/devices/heartbeat` | Backend's actual heartbeat path is `POST /api/v1/devices/status`, with body `{ device_id, timestamp }` (frontend currently sends the same body shape, just to the wrong path) | Fix the URL to `/api/v1/devices/status` |

### `recordingApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `list(params)` → `GET /api/v1/recordings` | **No such endpoint.** Only `GET /recordings/timeline/{cam_id}` exists, which requires `cam_id` in the path (not query) and returns `TimelineResponse`, not `PaginatedResponse<VideoSegment>` | Rewrite to call `recordingApi.getTimeline(camId, start, end)` (which already exists and is correct) instead of `.list()`. This is what's breaking `CameraDetailPage.tsx`'s "Today's recordings" section right now |
| `get(id)` → `GET /api/v1/recordings/${id}` | **No such endpoint** | Remove, or add backend support if a single-segment detail view is needed |
| `getDownloadUrl(id)` → `GET /api/v1/recordings/${id}/download` | Real path is `GET /recordings/{id}/presigned-url` | Fix the URL |
| `merge(data)` → `POST /api/v1/recordings/merge` | **Not implemented on backend** despite `MergeSegmentsRequest` schema existing | Backend work needed before this can be wired up at all |
| `downloadZip(ids)` → `POST /api/v1/recordings/download-zip` | **Not implemented on backend** despite `DownloadZipRequest` schema existing | Same — backend work needed first |

### `motionApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `list(params)` → `GET /api/v1/motion-events` | **No such endpoint.** Real path is `GET /api/v1/cameras/{cam_id}/motion` (camera in the path, not a query param) | Rewrite to take `camId` as a required path argument |
| `getWithMotion(camId, start, end)` → `GET /api/v1/motion-events/timeline/${camId}` | **No such endpoint.** Motion-overlaid timeline data comes from `GET /recordings/timeline/{cam_id}?include_motion=true` instead — there's no motion-only timeline route | Either reuse `recordingApi.getTimeline()` with `include_motion=true`, or this needs a dedicated backend endpoint if motion-only (no video segments) data is genuinely needed |

### `customerApi` / `geographyApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `customerApi.list()` typed `→ PaginatedResponse<Customer>` | Backend's `response_model` is `PaginatedResponse<CustomerListItem>` — missing `com_adr`, `gstn`, and all the joined name/count fields | Requires the backend fix in Section 3 Bug #3 first; then update the TS type to match whatever the backend actually returns |
| `customerApi.get(id)` typed `→ Customer` | Backend's `CustomerResponse` is missing the same joined fields | Same dependency on Bug #3 |
| `geographyApi.listCustomersByBA(baId)` typed `→ Customer[]` | Backend returns `CustomerListItem[]` (even more minimal — no `com_adr`/`gstn` either) | Same dependency on Bug #3, or accept the minimal shape and adjust the type |

### `cameraApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `getStreamToken(camId)` | Hits the broken duplicate route — see Section 3 Bug #1 | Blocked on backend fix; no frontend change will help until then |
| `CameraCreateRequest.strm_type_id: number` (required in TS) | Backend's Pydantic field is `strm_type_id: int \| None = None` (optional) | Not strictly broken (sending a value always works), but the TS type is needlessly stricter than the API requires — relax to `strm_type_id?: number` if camera creation without a stream type should be allowed |
| `CameraCreateRequest.is_active: boolean` (required in TS) | Backend's `CameraCreateRequest` Pydantic model **has no `is_active` field at all** — it's hardcoded to `True` in `CameraService.create()` | Harmless to keep sending (Pydantic silently ignores unknown fields by default), but it's dead weight in the type — consider removing it from the TS type for accuracy |

### `dashboardApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `getStats()` typed `→ DashboardStats` with fields `total_streams, active_cameras: string[], live_cameras: string[], all_added_streams, last_dn_tme: string[]` | Backend actually returns `{ total_cameras, online_cameras, offline_cameras, active_motion_events, total_recordings, total_customers }` — **completely different field names and types** (numbers, not string arrays) | Rewrite the `DashboardStats` TS interface from scratch to match; this looks like leftover typing from the old Django dashboard view, never updated for the FastAPI rewrite |
| `getCameraStatuses()` typed `→ Camera[]` | Backend returns minimal `{ cam_id, cam_name, status }[]`, not full `Camera` objects | Add a smaller `CameraStatusEntry`-style type (one already exists in `types/api.ts` — `CameraStatusEntry` — though its fields (`cam_loc`, `is_online`, `last_down_time`, `down_duration`) don't match the real `{cam_id, cam_name, status}` shape either; needs correcting too) |

### `alertApi`

| Frontend call | Backend reality | Fix |
|---|---|---|
| `list(params)` typed `→ PaginatedResponse<CameraAlert>` | Backend's `AlertListResponse` is `{ items, total }` only — **no `page`/`page_size`/`pages` fields**, unlike every other paginated endpoint in this API | Either add proper pagination fields to the backend response, or adjust the frontend type to a distinct `{ items, total }` shape instead of reusing `PaginatedResponse<T>` |

---

## 5. Suggested Fix Order

1. **Backend Bug #1** (stream-token) and **Bug #2** (duplicate health route cleanup) — quick,
   isolated, unblock camera viewing.
2. **`recordingApi`/`motionApi` rewiring** — these are the most broken (multiple endpoints
   that don't exist at all), and `CameraDetailPage.tsx` is already calling the broken ones in
   production right now.
3. **`deviceApi` fixes** — needed for the camera-creation form (`CameraAddPage.tsx`) to work
   end-to-end, including the new `streamTypes()` method.
4. **Backend Bug #3** (customer joined fields) — needed before `CustomersPage.tsx`'s plan/
   circle/BA columns and camera-count progress bar will ever show real data instead of blanks.
5. **`dashboardApi`/`DashboardStats` rewrite** — cosmetic compared to the above, but currently
   100% disconnected from what the backend sends.
