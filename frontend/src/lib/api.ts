// src/lib/api.ts
// Typed Axios wrapper. All API calls go through this module.
// Never call fetch() or axios directly in components.
//
// Key fixes vs. previous version:
//   - deviceApi.list()         → returns Device[] (not PaginatedResponse)
//   - deviceApi.streamTypes()  → added; GET /api/v1/devices/stream-types
//   - deviceApi.get()          → removed (backend has no GET /devices/{id})
//   - deviceApi.updateHeartbeat() → correct path /api/v1/devices/status
//   - recordingApi.list()      → removed; use getTimeline() instead
//   - recordingApi.get()       → removed (no backend endpoint)
//   - recordingApi.getDownloadUrl() → correct path /recordings/{id}/presigned-url
//   - motionApi.list()         → correct path /cameras/{cam_id}/motion
//   - motionApi.getWithMotion() → removed; use recordingApi.getTimeline() with include_motion=true
//   - alertApi.list()          → returns AlertListResponse (not PaginatedResponse)
//   - dashboardApi.getStats()  → returns DashboardStats (correct field names)
//   - dashboardApi.getCameraStatuses() → returns CameraStatusEntry[] (not Camera[])

import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import type {
  AlertListResponse,
  AppUser,
  BusinessArea,
  Camera,
  CameraAlert,
  CameraCreateRequest,
  CameraHealth,
  CameraStatusEntry,
  CameraUpdateRequest,
  ChangePasswordRequest,
  Circle,
  Customer,
  CustomerCreateRequest,
  DashboardStats,
  Device,
  DeviceTokenRequest,
  LoginRequest,
  LoginResponse,
  MotionEvent,
  PaginatedResponse,
  Plan,
  StreamToken,
  StreamTypeMaster,
  TimelineResponse,
  TokenRefreshResponse,
  UserCreateRequest,
  UserMe,
  VideoSegment,
} from "@/types/api";

// ── Axios instance ────────────────────────────────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach JWT from localStorage on every request.
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (config.url?.includes("/auth/login")) return config;
  try {
    const raw = localStorage.getItem("sarvanetra_session");
    if (raw) {
      const session = JSON.parse(raw) as { accessToken?: string };
      if (session.accessToken) {
        config.headers.Authorization = `Bearer ${session.accessToken}`;
      }
    }
  } catch {
    // ignore
  }
  return config;
});

// Handle 401 globally
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("sarvanetra_session");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// ── Helper ────────────────────────────────────────────────────────────────────

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: { message?: string } } | undefined;
    return data?.error?.message ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred";
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>("/api/v1/auth/login", data),

  refresh: (refreshToken: string) =>
    api.post<TokenRefreshResponse>("/api/v1/auth/refresh", {
      refresh_token: refreshToken,
    }),

  me: () => api.get<UserMe>("/api/v1/auth/me"),

  changePassword: (data: ChangePasswordRequest) =>
    api.post<void>("/api/v1/auth/change-password", data),

  logout: (refreshToken: string) =>
    api.post<void>("/api/v1/auth/logout", { refresh_token: refreshToken }),

  registerDeviceToken: (data: DeviceTokenRequest) =>
    api.post<void>("/api/v1/auth/device-token", data),
};

// ── Geography ─────────────────────────────────────────────────────────────────

export const geographyApi = {
  listCircles: () => api.get<Circle[]>("/api/v1/circles"),

  listBAs: (cirId: number) =>
    api.get<BusinessArea[]>(`/api/v1/circles/${cirId}/bas`),

  /** Returns CustomerListItem[] (minimal shape — backend joins names server-side now) */
  listCustomersByBA: (baId: number) =>
    api.get<Customer[]>(`/api/v1/bas/${baId}/customers`),
};

// ── Plans ─────────────────────────────────────────────────────────────────────

export const planApi = {
  list: () => api.get<Plan[]>("/api/v1/plans"),
};

// ── Customers ─────────────────────────────────────────────────────────────────

export const customerApi = {
  list: (params?: { ba_id?: number; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Customer>>("/api/v1/customers", { params }),

  get: (id: number) => api.get<Customer>(`/api/v1/customers/${id}`),

  create: (data: CustomerCreateRequest) =>
    api.post<Customer>("/api/v1/customers", data),

  update: (id: number, data: Partial<CustomerCreateRequest>) =>
    api.patch<Customer>(`/api/v1/customers/${id}`, data),
};

// ── Cameras ───────────────────────────────────────────────────────────────────

export const cameraApi = {
  /** com_id is REQUIRED by the backend */
  list: (params: {
    com_id: number;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<Camera>>("/api/v1/cameras", { params }),

  /** List cameras across all accessible companies (sysadmin / circle_admin use case).
   *  Internally issues one request per customer and merges — used on the dashboard. */
  listAll: (params?: { is_active?: boolean; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Camera>>("/api/v1/cameras", { params }),

  get: (camId: string) => api.get<Camera>(`/api/v1/cameras/${camId}`),

  create: (data: CameraCreateRequest) => api.post<Camera>("/api/v1/cameras", data),

  update: (camId: string, data: CameraUpdateRequest) =>
    api.patch<Camera>(`/api/v1/cameras/${camId}`, data),

  deactivate: (camId: string) =>
    api.post<{ message: string }>(`/api/v1/cameras/${camId}/deactivate`),

  reactivate: (camId: string) =>
    api.post<{ message: string }>(`/api/v1/cameras/${camId}/reactivate`),

  /** Returns StreamToken with expires_at (ISO string). */
  getStreamToken: (camId: string) =>
    api.get<StreamToken>(`/api/v1/cameras/${camId}/stream-token`),

  getHealth: (camId: string) =>
    api.get<CameraHealth>(`/api/v1/cameras/${camId}/health`),

  getLiveStatus: (camId: string) =>
    api.get<{ cam_id: string; ready: boolean; readers: number; source?: string }>(
      `/api/v1/cameras/${camId}/status`
    ),
};

// ── Devices ───────────────────────────────────────────────────────────────────

export const deviceApi = {
  /**
   * Returns a flat Device[] (NOT paginated).
   * Server caps at 200 rows; page/page_size params are ignored by backend.
   */
  list: (params?: { staging_status?: string }) =>
    api.get<Device[]>("/api/v1/devices", { params }),

  /** Reference data for camera-add form stream-type dropdown. */
  streamTypes: () => api.get<StreamTypeMaster[]>("/api/v1/devices/stream-types"),

  /** Register / update a device (MQTT announce). */
  capture: (data: { device_no: string; dev_name?: string; dev_loc?: string }) =>
    api.post<{ message: string }>("/api/v1/devices/capture", data),

  /** MQTT heartbeat — correct path is /devices/status, NOT /devices/heartbeat */
  updateHeartbeat: (device_id: string, timestamp: string) =>
    api.post<{ message: string }>("/api/v1/devices/status", { device_id, timestamp }),
};

// ── Recordings ────────────────────────────────────────────────────────────────

export const recordingApi = {
  /**
   * Primary recording query endpoint.
   * Returns a timeline of segments in [start, end] with overlapping motion events.
   * start and end must be ISO datetime strings.
   */
  getTimeline: (camId: string, start: string, end: string, includeMotion = true) =>
    api.get<TimelineResponse>(`/api/v1/recordings/timeline/${camId}`, {
      params: { start, end, include_motion: includeMotion },
    }),

  /** Stream a video segment directly (supports HTTP Range). */
  getVideoUrl: (segmentId: number): string =>
    `${import.meta.env.VITE_API_URL ?? ""}/api/v1/recordings/${segmentId}/video`,

  /**
   * Get a presigned MinIO URL for direct download (time-limited).
   * expires = seconds until link expires (default 3600, max 86400).
   */
  getPresignedUrl: (segmentId: number, expires = 3600) =>
    api.get<{ url: string; expires_in: number }>(
      `/api/v1/recordings/${segmentId}/presigned-url`,
      { params: { expires } }
    ),
};

// ── Motion Events ─────────────────────────────────────────────────────────────

export const motionApi = {
  /**
   * List motion events for a specific camera.
   * cam_id goes in the URL path, not as a query param.
   *
   * For motion events overlaid on video timeline, use
   * recordingApi.getTimeline(camId, start, end, true) instead.
   */
  list: (
    camId: string,
    params?: {
      start?: string;
      end?: string;
      is_active?: boolean;
      page?: number;
      page_size?: number;
    }
  ) =>
    api.get<PaginatedResponse<MotionEvent>>(`/api/v1/cameras/${camId}/motion`, {
      params,
    }),
};

// ── Alerts ────────────────────────────────────────────────────────────────────

export const alertApi = {
  /**
   * NOTE: backend returns AlertListResponse = { items, total }
   * — NOT a full PaginatedResponse (no page/page_size/pages fields).
   * Use skip/limit instead of page/page_size.
   */
  list: (params?: { skip?: number; limit?: number }) =>
    api.get<AlertListResponse>("/api/v1/alerts", { params }),

  acknowledge: (id: number) =>
    api.patch<CameraAlert>(`/api/v1/alerts/${id}/acknowledge`),
};

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const dashboardApi = {
  /**
   * Returns DashboardStats:
   * { total_cameras, online_cameras, offline_cameras,
   *   active_motion_events, total_recordings, total_customers }
   * All numbers — NOT the old Django { active_cameras: string[], live_cameras: string[] } shape.
   */
  getStats: () => api.get<DashboardStats>("/api/v1/dashboard/stats"),

  /**
   * Returns CameraStatusEntry[] — NOT full Camera objects.
   * Shape: { cam_id, cam_name, status: "up" | "down" }[]
   */
  getCameraStatuses: () =>
    api.get<CameraStatusEntry[]>("/api/v1/dashboard/camera-status"),
};

// ── Users ─────────────────────────────────────────────────────────────────────

export const userApi = {
  list: () => api.get<AppUser[]>("/api/v1/users/"),

  get: (id: number) => api.get<AppUser>(`/api/v1/users/${id}`),

  create: (data: UserCreateRequest) => api.post<AppUser>("/api/v1/users/", data),

  update: (id: number, data: Partial<UserCreateRequest> & { is_active?: boolean }) =>
    api.put<AppUser>(`/api/v1/users/${id}`, data),

  deactivate: (id: number) =>
    api.delete<void>(`/api/v1/users/${id}`),
};

export default api;