// src/types/next-auth.d.ts
// NextAuth v5 type augmentation.
// Uses the exact pattern confirmed to work:
//   - User.id stays string (NextAuth v5 core requirement)
//   - @auth/core/jwt for JWT interface (not next-auth/jwt)
//   - Session.user.id is number (cast in the session callback)
//   - com_name removed — not in sv_users schema
//   - refresh_token + accessTokenExpiresAt added for token rotation

import { DefaultSession } from "next-auth";
import type { UserRole } from "@/types/api";

declare module "next-auth" {
  interface Session {
    accessToken: string;
    refreshToken: string;
    accessTokenExpiresAt: number;       // Unix timestamp (seconds)
    error?: "RefreshFailed";
    user: DefaultSession["user"] & {
      id: number;
      role: UserRole;
      com_id: number | null;
      cir_id: number | null;
      ba_id: number | null;
    };
  }

  interface User {
    id: string;                         // NextAuth v5 requires string
    accessToken: string;
    refreshToken: string;
    accessTokenExpiresAt: number;
    role: UserRole;
    com_id: number | null;
    cir_id: number | null;
    ba_id: number | null;
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    accessToken: string;
    refreshToken: string;
    accessTokenExpiresAt: number;
    role: UserRole;
    userId: number;                     // Stored as number after Number(user.id) cast
    com_id: number | null;
    cir_id: number | null;
    ba_id: number | null;
    error?: "RefreshFailed";
  }
}

export {};