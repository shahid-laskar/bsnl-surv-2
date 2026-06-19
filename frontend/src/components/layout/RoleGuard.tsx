// src/components/layout/RoleGuard.tsx
// CLIENT-SIDE ONLY — for UX, not security.
// API enforces all permissions server-side.
// Never rely on this guard alone.

"use client";

import { useSession } from "next-auth/react";
import type { UserRole } from "@/types/api";
import { hasRole } from "@/lib/utils";

interface RoleGuardProps {
  roles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ roles, children, fallback = null }: RoleGuardProps) {
  const { data: session } = useSession();
  const userRole = session?.user?.role;

  if (!userRole || !hasRole(userRole, roles)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
