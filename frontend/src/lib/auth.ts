// src/lib/auth.ts
// NextAuth v5 configuration.
// Uses Credentials provider against our FastAPI /api/v1/auth/login endpoint.
// Stores JWT token in the session for use by the API client.

import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { UserRole } from "@/types/api";

// Extend NextAuth types to carry our custom fields
declare module "next-auth" {
  interface Session {
    accessToken: string;
    user: {
      id: number;
      name: string;
      email: string;
      role: UserRole;
      com_id: number | null;
      com_name: string | null;
      cir_id: number | null;
      ba_id: number | null;
    };
  }

  interface User {
    id: number;
    accessToken: string;
    role: UserRole;
    com_id: number | null;
    com_name: string | null;
    cir_id: number | null;
    ba_id: number | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string;
    role: UserRole;
    userId: number;
    com_id: number | null;
    com_name: string | null;
    cir_id: number | null;
    ba_id: number | null;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
          const response = await fetch(`${API_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: credentials.username,
              password: credentials.password,
            }),
          });

          if (!response.ok) return null;

          const data = (await response.json()) as {
            access_token: string;
            user: {
              id: number;
              username: string;
              first_name: string;
              last_name: string;
              email: string;
              role: UserRole;
              com_id: number | null;
              com_name: string | null;
              cir_id: number | null;
              ba_id: number | null;
            };
          };

          return {
            id: data.user.id,
            name: `${data.user.first_name} ${data.user.last_name}`.trim() || data.user.username,
            email: data.user.email,
            accessToken: data.access_token,
            role: data.user.role,
            com_id: data.user.com_id,
            com_name: data.user.com_name,
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
    maxAge: 60 * 60 * 8, // 8 hours
  },

  callbacks: {
    async jwt({ token, user }) {
      // On initial sign-in, persist user fields into the JWT
      if (user) {
        token.accessToken = user.accessToken;
        token.role = user.role;
        token.userId = user.id;
        token.com_id = user.com_id;
        token.com_name = user.com_name;
        token.cir_id = user.cir_id;
        token.ba_id = user.ba_id;
      }
      return token;
    },

    async session({ session, token }) {
      // Expose token fields on the session object
      session.accessToken = token.accessToken;
      session.user.id = token.userId;
      session.user.role = token.role;
      session.user.com_id = token.com_id;
      session.user.com_name = token.com_name;
      session.user.cir_id = token.cir_id;
      session.user.ba_id = token.ba_id;
      return session;
    },
  },
});
