// src/contexts/AuthContext.tsx
//
// Custom auth context replacing next-auth.
// Stores JWT tokens in localStorage and handles:
//   - login / logout
//   - silent token refresh (same logic as the old NextAuth jwt() callback)
//   - exposes a `session` object similar to what next-auth/react useSession() returned

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { LoginResponse, TokenRefreshResponse, UserRole } from "@/types/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  com_id: number | null;
  cir_id: number | null;
  ba_id: number | null;
}

export interface AuthSession {
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number; // unix seconds
  error?: "RefreshFailed";
}

interface AuthContextValue {
  session: AuthSession | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STORAGE_KEY = "sarvanetra_session";
const REFRESH_BUFFER_SECONDS = 300; // 5 min — same as old NextAuth config
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Persistence helpers ───────────────────────────────────────────────────────

function saveSession(session: AuthSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// ── Token refresh ─────────────────────────────────────────────────────────────

async function refreshAccessToken(refreshToken: string): Promise<{
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
} | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as TokenRefreshResponse;
    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      accessTokenExpiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
    };
  } catch {
    return null;
  }
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">(
    "loading",
  );
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Schedule next silent refresh ──────────────────────────────────────────

  const scheduleRefresh = useCallback((sess: AuthSession) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

    const nowSeconds = Math.floor(Date.now() / 1000);
    const secondsUntilRefresh = sess.accessTokenExpiresAt - nowSeconds - REFRESH_BUFFER_SECONDS;
    const delayMs = Math.max(secondsUntilRefresh * 1000, 0);

    refreshTimerRef.current = setTimeout(async () => {
      const refreshed = await refreshAccessToken(sess.refreshToken);
      if (!refreshed) {
        setSession((prev) => (prev ? { ...prev, error: "RefreshFailed" } : null));
        return;
      }
      const updated: AuthSession = {
        ...sess,
        accessToken: refreshed.accessToken,
        refreshToken: refreshed.refreshToken,
        accessTokenExpiresAt: refreshed.accessTokenExpiresAt,
        error: undefined,
      };
      saveSession(updated);
      setSession(updated);
      scheduleRefresh(updated);
    }, delayMs);
  }, []);

  // ── Bootstrap from localStorage ───────────────────────────────────────────

  useEffect(() => {
    const stored = loadSession();
    if (!stored) {
      setStatus("unauthenticated");
      return;
    }

    const nowSeconds = Math.floor(Date.now() / 1000);
    const secondsRemaining = stored.accessTokenExpiresAt - nowSeconds;

    if (secondsRemaining > REFRESH_BUFFER_SECONDS) {
      // Token still valid — use it and schedule a refresh
      setSession(stored);
      setStatus("authenticated");
      scheduleRefresh(stored);
    } else {
      // Token near/past expiry — try to refresh immediately
      void refreshAccessToken(stored.refreshToken).then((refreshed) => {
        if (!refreshed) {
          clearSession();
          setStatus("unauthenticated");
          return;
        }
        const updated: AuthSession = {
          ...stored,
          accessToken: refreshed.accessToken,
          refreshToken: refreshed.refreshToken,
          accessTokenExpiresAt: refreshed.accessTokenExpiresAt,
          error: undefined,
        };
        saveSession(updated);
        setSession(updated);
        setStatus("authenticated");
        scheduleRefresh(updated);
      });
    }

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── login ─────────────────────────────────────────────────────────────────

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        throw new Error("Invalid username or password");
      }

      const data = (await res.json()) as LoginResponse;

      const newSession: AuthSession = {
        user: {
          id: data.user.id,
          name: `${data.user.first_name} ${data.user.last_name}`.trim() || data.user.username,
          email: data.user.email,
          role: data.user.role,
          com_id: data.user.com_id,
          cir_id: data.user.cir_id,
          ba_id: data.user.ba_id,
        },
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        accessTokenExpiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
      };

      saveSession(newSession);
      setSession(newSession);
      setStatus("authenticated");
      scheduleRefresh(newSession);
    },
    [scheduleRefresh],
  );

  // ── logout ────────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

    // Best-effort: revoke refresh token on the backend
    if (session?.refreshToken) {
      try {
        await fetch(`${API_URL}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.accessToken}`,
          },
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        });
      } catch {
        // Ignore — we're logging out anyway
      }
    }

    clearSession();
    setSession(null);
    setStatus("unauthenticated");
  }, [session]);

  const value = useMemo(
    () => ({ session, status, login, logout }),
    [session, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

// Convenience: mirrors next-auth/react useSession() shape for easier migration
export function useSession() {
  const { session, status } = useAuth();
  return { data: session, status };
}
