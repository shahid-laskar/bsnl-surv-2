// src/lib/api.ts
// Typed Axios wrapper. All API calls go through this module.
// Never call fetch() or axios directly in components.

import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import type {
  AppUser,
  Camera,
  CameraAlert,
  CameraCreateRequest,
  CameraHealth,
  CameraUpdateRequest,
  ChangePasswordRequest,
  Circle,
  BusinessArea,
  Customer,
  CustomerCreateRequest,
  DashboardStats,
  DeviceTokenRequest,
  Device,
  LoginRequest,
  LoginResponse,
  MergeRequest,
  MotionEvent,
  PaginatedResponse,
  RecordingDownloadResponse,
  StreamToken,
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
// Reads directly from storage so we don't need a React context reference here.
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  // Skip auth header for login endpoint
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
    // Ignore
  }
  return config;
});

// Handle 401 globally — clear localStorage and redirect to /login
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

// ── Helper to extract error message ──────────────────────────────────────────

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

  listBAs: (cirId: number) => api.get<BusinessArea[]>(`/api/v1/circles/${cirId}/bas`),

  listCustomersByBA: (baId: number) =>
    api.get<Customer[]>(`/api/v1/bas/${baId}/customers`),
};

// ── Customers ─────────────────────────────────────────────────────────────────

export const customerApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Customer>>("/api/v1/customers", { params }),

  get: (id: number) => api.get<Customer>(`/api/v1/customers/${id}`),

  create: (data: CustomerCreateRequest) =>
    api.post<Customer>("/api/v1/customers", data),

  update: (id: number, data: Partial<CustomerCreateRequest>) =>
    api.patch<Customer>(`/api/v1/customers/${id}`, data),
};

// ── Cameras ───────────────────────────────────────────────────────────────────

export const cameraApi = {
  list: (params?: {
    com_id?: number;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<Camera>>("/api/v1/cameras", { params }),

  get: (camId: string) => api.get<Camera>(`/api/v1/cameras/${camId}`),

  create: (data: CameraCreateRequest) => api.post<Camera>("/api/v1/cameras", data),

  update: (camId: string, data: CameraUpdateRequest) =>
    api.patch<Camera>(`/api/v1/cameras/${camId}`, data),

  deactivate: (camId: string) =>
    api.delete<{ message: string }>(`/api/v1/cameras/${camId}`),

  reactivate: (camId: string) =>
    api.post<Camera>(`/api/v1/cameras/${camId}/reactivate`),

  getStreamToken: (camId: string) =>
    api.get<StreamToken>(`/api/v1/cameras/${camId}/stream-token`),

  getHealth: (camId: string) =>
    api.get<CameraHealth>(`/api/v1/cameras/${camId}/health`),

  // Returns JPEG snapshot URL
  getSnapshotUrl: (camId: string) =>
    `${import.meta.env.VITE_API_URL ?? ""}/api/v1/cameras/${camId}/snapshot`,
};

// ── Devices ───────────────────────────────────────────────────────────────────

export const deviceApi = {
  list: (params?: { staging_status?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Device>>("/api/v1/devices", { params }),

  get: (id: number) => api.get<Device>(`/api/v1/devices/${id}`),

  updateHeartbeat: (deviceId: string, timestamp: string) =>
    api.post<{ success: boolean }>("/api/v1/devices/heartbeat", {
      device_id: deviceId,
      timestamp,
    }),
};

// ── Recordings ────────────────────────────────────────────────────────────────

export const recordingApi = {
  getTimeline: (camId: string, start: string, end: string) =>
    api.get<TimelineResponse>(`/api/v1/recordings/timeline/${camId}`, {
      params: { start, end },
    }),

  list: (params: {
    cam_id?: string;
    start?: string;
    end?: string;
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<VideoSegment>>("/api/v1/recordings", { params }),

  get: (id: number) => api.get<VideoSegment>(`/api/v1/recordings/${id}`),

  getDownloadUrl: (id: number) =>
    api.get<RecordingDownloadResponse>(`/api/v1/recordings/${id}/download`),

  merge: (data: MergeRequest) =>
    api.post<Blob>("/api/v1/recordings/merge", data, { responseType: "blob" }),

  downloadZip: (segmentIds: number[]) =>
    api.post<Blob>(
      "/api/v1/recordings/download-zip",
      { segment_ids: segmentIds },
      { responseType: "blob" },
    ),
};

// ── Motion Events ─────────────────────────────────────────────────────────────

export const motionApi = {
  list: (params: {
    cam_id?: string;
    date?: string;
    active_only?: boolean;
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<MotionEvent>>("/api/v1/motion-events", { params }),

  getWithMotion: (camId: string, start: string, end: string) =>
    api.get<TimelineResponse>(`/api/v1/motion-events/timeline/${camId}`, {
      params: { start, end },
    }),
};

// ── Alerts ────────────────────────────────────────────────────────────────────

export const alertApi = {
  list: (params?: {
    status?: "up" | "down";
    cam_id?: string;
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<CameraAlert>>("/api/v1/alerts", { params }),

  acknowledge: (id: number) =>
    api.patch<CameraAlert>(`/api/v1/alerts/${id}/acknowledge`),
};

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const dashboardApi = {
  getStats: () => api.get<DashboardStats>("/api/v1/dashboard/stats"),

  getCameraStatuses: () =>
    api.get<Camera[]>("/api/v1/dashboard/camera-status"),
};

// ── Users ─────────────────────────────────────────────────────────────────────

export const userApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<AppUser>>("/api/v1/users", { params }),

  get: (id: number) => api.get<AppUser>(`/api/v1/users/${id}`),

  create: (data: UserCreateRequest) => api.post<AppUser>("/api/v1/users", data),

  update: (id: number, data: Partial<UserCreateRequest>) =>
    api.patch<AppUser>(`/api/v1/users/${id}`, data),

  deactivate: (id: number) =>
    api.delete<{ message: string }>(`/api/v1/users/${id}`),
};

export default api;
