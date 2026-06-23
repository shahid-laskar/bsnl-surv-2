
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { UserRole, LoginResponse, TokenRefreshResponse } from "@/types/api";

// Server-side fetches use the internal Docker network URL when available.
// Client-side fetches always use NEXT_PUBLIC_API_URL.
const API_URL =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// Refresh when fewer than this many seconds remain on the access token.
const REFRESH_BUFFER_SECONDS = 300; // 5 minutes

// ── Token refresh helper ──────────────────────────────────────────────────────

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
      refreshToken: data.refresh_token,           // Rotated — store the new one
      accessTokenExpiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
    };
  } catch {
    return null;
  }
}

// ── NextAuth config ───────────────────────────────────────────────────────────

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) return null;

        try {
          const res = await fetch(`${API_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: credentials.username,
              password: credentials.password,
            }),
          });

          if (!res.ok) return null;

          const data = (await res.json()) as LoginResponse;

          return {
            // NextAuth requires id to be string
            id: String(data.user.id),
            name:
              `${data.user.first_name} ${data.user.last_name}`.trim() ||
              data.user.username,
            email: data.user.email,
            // Custom fields (declared in src/types/next-auth.d.ts)
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            accessTokenExpiresAt:
              Math.floor(Date.now() / 1000) + data.expires_in,
            role: data.user.role,
            com_id: data.user.com_id,
            cir_id: data.user.cir_id,
            ba_id: data.user.ba_id,
          };
        } catch {
          return null;
        }
      },
    }),
  ],

  pages: {
    signIn: "/login",
    error: "/login",
  },

  session: {
    strategy: "jwt",
    // Must be >= refresh token lifetime (30 days per backend config)
    maxAge: 60 * 60 * 24 * 30,
  },

  callbacks: {
    async jwt({ token, user }) {
      // ── Initial sign-in: populate JWT from the User object ────────────────
      if (user) {
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.accessTokenExpiresAt = user.accessTokenExpiresAt;
        token.role = user.role;
        token.userId = Number(user.id);   // Convert string → number for our use
        token.com_id = user.com_id;
        token.cir_id = user.cir_id;
        token.ba_id = user.ba_id;
        return token;
      }

      // ── Subsequent requests: refresh access token if nearing expiry ───────
      const nowSeconds = Math.floor(Date.now() / 1000);
      const secondsRemaining = token.accessTokenExpiresAt - nowSeconds;

      if (secondsRemaining > REFRESH_BUFFER_SECONDS) {
        // Still valid — return unchanged
        return token;
      }

      // Attempt rotation
      const refreshed = await refreshAccessToken(token.refreshToken);

      if (!refreshed) {
        // Signal the session layer so the UI can show a re-login prompt
        return { ...token, error: "RefreshFailed" as const };
      }

      return {
        ...token,
        accessToken: refreshed.accessToken,
        refreshToken: refreshed.refreshToken,
        accessTokenExpiresAt: refreshed.accessTokenExpiresAt,
        error: undefined,
      };
    },

    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.refreshToken = token.refreshToken;
      session.accessTokenExpiresAt = token.accessTokenExpiresAt;      
      (session.user as any).id = Number(token.userId);
      session.user.role = token.role;
      session.user.com_id = token.com_id;
      session.user.cir_id = token.cir_id;
      session.user.ba_id = token.ba_id;
      if (token.error) session.error = token.error;
      return session;
    },
  },
});