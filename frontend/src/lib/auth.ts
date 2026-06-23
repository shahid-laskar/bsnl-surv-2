// src/lib/auth.ts
// Re-exports from AuthContext for convenience.
// The full auth logic now lives in src/contexts/AuthContext.tsx.
export { useAuth, useSession, AuthProvider } from "@/contexts/AuthContext";
export type { AuthSession, AuthUser } from "@/contexts/AuthContext";
