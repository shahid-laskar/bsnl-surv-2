// src/lib/utils.ts

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";

// shadcn/ui standard cn helper
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// ── Date / Time ───────────────────────────────────────────────────────────────

/** Format an ISO string to a human-readable date-time in IST */
export function formatDateTime(iso: string): string {
  try {
    return format(parseISO(iso), "dd MMM yyyy, HH:mm:ss");
  } catch {
    return iso;
  }
}

/** Format an ISO string to time only */
export function formatTime(iso: string): string {
  try {
    return format(parseISO(iso), "HH:mm:ss");
  } catch {
    return iso;
  }
}

/** Format an ISO string to date only */
export function formatDate(iso: string): string {
  try {
    return format(parseISO(iso), "dd MMM yyyy");
  } catch {
    return iso;
  }
}

/** How long ago */
export function timeAgo(iso: string): string {
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

/** Format seconds duration → "1h 23m 45s" */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/** Format bytes → human-readable */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i] ?? "B"}`;
}

// ── Role checks ───────────────────────────────────────────────────────────────

import type { UserRole } from "@/types/api";

const ROLE_HIERARCHY: Record<UserRole, number> = {
  sysadmin: 5,
  circle_admin: 4,
  ba_admin: 3,
  cust_admin: 2,
  viewer: 1,
};

export function hasRole(userRole: UserRole, requiredRoles: UserRole[]): boolean {
  return requiredRoles.includes(userRole);
}

export function hasMinimumRole(userRole: UserRole, minimumRole: UserRole): boolean {
  return (ROLE_HIERARCHY[userRole] ?? 0) >= (ROLE_HIERARCHY[minimumRole] ?? 0);
}

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    sysadmin: "System Admin",
    circle_admin: "Circle Admin",
    ba_admin: "BA Admin",
    cust_admin: "Customer Admin",
    viewer: "Viewer",
  };
  return labels[role] ?? role;
}

// ── Misc ──────────────────────────────────────────────────────────────────────

/** Truncate a string with ellipsis */
export function truncate(str: string, maxLength: number): string {
  return str.length > maxLength ? `${str.slice(0, maxLength)}…` : str;
}

/** Download a blob as a file */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Build today's ISO date range for recordings filter */
export function todayRange(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000 - 1);
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}
