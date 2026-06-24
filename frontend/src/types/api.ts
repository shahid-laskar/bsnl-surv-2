// src/types/api.ts
// These types mirror backend Pydantic schemas exactly.
// When a backend schema changes, this file must change too.

// ── Common ────────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ErrorDetail {
  code: string;
  message: string;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export type UserRole =
  | "sysadmin"
  | "circle_admin"
  | "ba_admin"
  | "cust_admin"
  | "viewer";

// Which scope fields each role must have (enforced server-side):
//   sysadmin       → none required
//   circle_admin   → cir_id required
//   ba_admin       → cir_id + ba_id required
//   cust_admin     → com_id required (cir_id/ba_id auto-set from customer)
//   viewer         → com_id required (cir_id/ba_id auto-set from customer)

export interface LoginRequest {
  username: string;
  password: string;
  device_id?: string;
}

/** Exact shape returned by POST /api/v1/auth/login */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserMe;
}

/** Exact shape returned by POST /api/v1/auth/refresh */
export interface TokenRefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

/** User profile — matches sv_users columns returned by GET /api/v1/auth/me */
export interface UserMe {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  com_id: number | null;
  cir_id: number | null;
  ba_id: number | null;
  is_active: boolean;
  date_joined: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface DeviceTokenRequest {
  token: string;
  platform: "android" | "ios" | "web";
}

// ── Geography ─────────────────────────────────────────────────────────────────

export interface Circle {
  id: number;
  cir_name: string;
  cir_code: string;
}

export interface BusinessArea {
  id: number;
  ba_name: string;
  ba_code: string;
  cir_id: number;
}

// ── Customer ──────────────────────────────────────────────────────────────────

/**
 * Full customer shape — returned by GET /customers, GET /customers/{id},
 * POST /customers, PATCH /customers/{id}.
 * Includes joined names and camera usage stats.
 */
export interface Customer {
  id: number;
  com_name: string;
  com_adr: string;
  gstn: string | null;
  cir_id: number;
  ba_id: number;
  plan_id: number;
  // Joined / computed fields populated by the service layer
  cir_name: string;
  ba_name: string;
  plan_name: string;
  camera_count: number;
  camera_limit: number;
}

export interface CustomerCreateRequest {
  com_name: string;
  com_adr: string;
  gstn?: string;
  cir_id: number;
  ba_id: number;
  plan_id: number;
}

export interface Plan {
  id: number;
  plan_name: string;
  cam_limit: number;
}

// ── Device ────────────────────────────────────────────────────────────────────

export interface Device {
  id: number;
  device_id: string;
  dev_name: string | null;
  dev_loc: string | null;
  staging_status: string | null;
  status_log: string | null;
  mqtt_status: string | null;
  mqtt_update: string | null;
}

export interface StreamTypeMaster {
  id: number;
  strm_type: string;
  remark: string | null;
}

// ── Camera ────────────────────────────────────────────────────────────────────

export interface Camera {
  id: number;
  cam_id: string;
  cam_name: string;
  cam_loc: string;
  cam_make: string;
  cam_strm1: string;
  cam_strm2: string | null;
  cam_strm3: string | null;
  cam_usrname: string;
  is_active: boolean;
  motion_active: boolean;
  cam_onvif: number | null;
  com_id: number;
  cir_id: number;
  ba_id: number;
  device_id: number;
  strm_type_id: number | null;
  upd_time: string;
  // Runtime: populated client-side from dashboard/camera-status
  is_online?: boolean;
  last_seen?: string | null;
}

export interface CameraCreateRequest {
  cam_name: string;
  cam_loc: string;
  cam_make: string;
  cam_strm1: string;
  cam_strm2?: string;
  cam_strm3?: string;
  cam_usrname: string;
  cam_pass: string;
  cam_onvif?: number;
  strm_type_id?: number; // optional on backend
  com_id: number;
  device_id: number;
  motion_active?: boolean;
}

export interface CameraUpdateRequest {
  cam_name?: string;
  cam_loc?: string;
  cam_make?: string;
  cam_strm1?: string;
  cam_strm2?: string | null;
  cam_strm3?: string | null;
  cam_usrname?: string;
  cam_pass?: string;
  cam_onvif?: number | null;
  is_active?: boolean;
  motion_active?: boolean;
}

export interface StreamToken {
  token: string;
  stream_url: string;
  cam_id: string;
  /** ISO datetime string */
  expires_at: string;
}

export interface CameraHealth {
  current_status: "up" | "down";
  last_change: string;
  last_downtime_duration: string | null;
}

// ── Recording ─────────────────────────────────────────────────────────────────

export interface VideoSegment {
  id: number;
  cam_id: string | null;
  start_time: string;
  end_time: string;
  duration: number;
  file_path: string;
  file_size: number;
  minio_bucket: string;
  created_at: string;
  start_timestamp: number;
  end_timestamp: number;
}

export interface TimelineResponse {
  cam_id: string;
  camera_name: string;
  segments: TimelineSegment[];
  total_duration: number;
  segment_count: number;
  start_date: string;
  end_date: string;
}

export interface TimelineSegment {
  id: number;
  start_time: number;
  end_time: number;
  duration: number;
  cumulative_start: number;
  cumulative_end: number;
  /** Already-built URL: GET /api/v1/recordings/{id}/video */
  url: string;
  file_path: string;
  readable_start: string;
  readable_end: string;
  motion_events: MotionEventSummary[];
  motion_count: number;
}

export interface MotionEventSummary {
  id: number;
  start: number;
  end: number | null;
  duration: number | null;
  is_active: boolean;
  readable_start: string;
  readable_end: string;
}

// ── Motion ────────────────────────────────────────────────────────────────────

export interface MotionEvent {
  id: number;
  camera_id: number;
  motion_start: string;
  motion_end: string | null;
  is_active: boolean;
  duration_seconds: number | null;
}

// ── Alerts ────────────────────────────────────────────────────────────────────

export type AlertStatus = "up" | "down";

/**
 * Shape returned by GET /api/v1/alerts and PATCH /api/v1/alerts/{id}/acknowledge.
 * NOTE: the list response is { items, total } — NOT a full PaginatedResponse.
 */
export interface CameraAlert {
  id: number;
  camera_id: number;
  cam_name: string | null;
  status: AlertStatus;
  timestamp: string;
  duration: string | null;
  acknowledged: boolean;
}

/** Non-paginated alert list — matches the backend's AlertListResponse exactly */
export interface AlertListResponse {
  items: CameraAlert[];
  total: number;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

/**
 * Exact shape returned by GET /api/v1/dashboard/stats.
 * All numbers — no string arrays like the old Django view.
 */
export interface DashboardStats {
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  active_motion_events: number;
  total_recordings: number;
  total_customers: number;
}

/**
 * One entry from GET /api/v1/dashboard/camera-status.
 * Returns a flat list of { cam_id, cam_name, status } — NOT full Camera objects.
 */
export interface CameraStatusEntry {
  cam_id: string;
  cam_name: string;
  status: "up" | "down";
}

// ── Users ─────────────────────────────────────────────────────────────────────

export interface AppUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  role: UserRole;
  com_id: number | null;
  cir_id: number | null;
  ba_id: number | null;
  date_joined: string;
}

/**
 * UserCreateRequest — scope fields required per role:
 *   sysadmin       → none
 *   circle_admin   → cir_id
 *   ba_admin       → cir_id + ba_id
 *   cust_admin     → com_id  (cir_id/ba_id auto-inherited from customer)
 *   viewer         → com_id  (cir_id/ba_id auto-inherited from customer)
 */
export interface UserCreateRequest {
  username: string;
  password: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  com_id?: number;
  cir_id?: number;
  ba_id?: number;
}
