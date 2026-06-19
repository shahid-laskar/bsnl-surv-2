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

/**
 * User profile — matches sv_users columns returned by GET /api/v1/auth/me
 * NOTE: com_name is NOT returned by the new backend (no Django join).
 *       Fetch customer name separately via GET /api/v1/customers/{com_id} if needed.
 */
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

export interface Customer {
  id: number;
  com_name: string;
  com_adr: string;
  gstn: string | null;
  cir_id: number;
  cir_name: string;
  ba_id: number;
  ba_name: string;
  plan_id: number;
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

// ── Device ────────────────────────────────────────────────────────────────────

export type DeviceStatus = "NEW" | "online" | "offline";

export interface Device {
  id: number;
  device_id: string;
  dev_name: string | null;
  dev_loc: string | null;
  staging_status: DeviceStatus;
  status_log: string | null;
  mqtt_status: string | null;
  mqtt_update: string | null;
}

// ── Camera ────────────────────────────────────────────────────────────────────

export type StreamType = "RTSP" | "RTMP" | "RTSP CLOUD";

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
  strm_type: StreamType;
  com_id: number;
  com_name: string;
  cir_id: number;
  ba_id: number;
  device_id: number;
  upd_time: string;
  // Runtime status (from MediaMTX, not DB)
  is_online: boolean;
  last_seen: string | null;
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
  strm_type_id: number;
  com_id: number;
  device_id: number;
  is_active: boolean;
  motion_active: boolean;
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
  expires_at: string;
}

export interface CameraHealth {
  cam_id: string;
  is_online: boolean;
  motion_health_status: "UP" | "DOWN" | null;
  last_motion_at: string | null;
  mediamtx_ready: boolean;
  last_seen: string | null;
}

// ── Recording ─────────────────────────────────────────────────────────────────

export interface VideoSegment {
  id: number;
  camera_id: number;
  cam_id: string;
  cam_name: string;
  start_time: string;
  end_time: string;
  duration: number;
  file_path: string;
  file_size: number;
  minio_bucket: string;
  created_at: string;
  // Computed
  readable_start: string;
  readable_end: string;
  start_timestamp: number;
  end_timestamp: number;
}

export interface RecordingDownloadResponse {
  url: string;
  expires_at: string;
}

export interface MergeRequest {
  segment_ids: number[];
}

export interface TimelineResponse {
  cam_id: string;
  camera_name: string;
  segments: TimelineSegment[];
  total_duration: number;
  start_date: string;
  end_date: string;
  segment_count: number;
}

export interface TimelineSegment {
  id: number;
  start_time: number;
  end_time: number;
  duration: number;
  cumulative_start: number;
  cumulative_end: number;
  url: string;
  file_path: string;
  readable_start: string;
  readable_end: string;
  motion_events?: MotionEventSummary[];
  motion_count?: number;
}

// ── Motion ────────────────────────────────────────────────────────────────────

export interface MotionEvent {
  id: number;
  camera_id: number;
  cam_id: string;
  cam_name: string;
  motion_start: string;
  motion_end: string | null;
  is_active: boolean;
  created_at: string;
  duration: number | null;
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

// ── Alerts ────────────────────────────────────────────────────────────────────

export type AlertStatus = "up" | "down";
export type AlertSeverity = "info" | "warning" | "critical";

export interface CameraAlert {
  id: number;
  camera_id: number;
  cam_id: string;
  cam_name: string;
  cam_loc: string;
  status: AlertStatus;
  timestamp: string;
  duration: string | null;
  acknowledged: boolean;
  acknowledged_at: string | null;
}

/** Camera status snapshot from CameraHealth DB model (last known up/down state) */
export interface CameraAlertHealth {
  cam_id: string;
  current_status: AlertStatus;
  last_change: string;
  last_downtime_duration: string | null;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_streams: number;
  active_cameras: string[];
  live_cameras: string[];
  all_added_streams: number;
  last_dn_tme: string[];
}

export interface CameraStatusEntry {
  cam_id: string;
  cam_name: string;
  cam_loc: string;
  is_online: boolean;
  last_down_time: string | null;
  down_duration: string | null;
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
