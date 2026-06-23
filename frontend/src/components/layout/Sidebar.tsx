// src/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  LayoutDashboard,
  Camera,
  Film,
  Activity,
  Bell,
  Users,
  Building2,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { cn, hasRole, getRoleLabel } from "@/lib/utils";
import type { UserRole } from "@/types/api";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  roles: UserRole[]; // empty = all roles
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    roles: [],
  },
  {
    href: "/cameras",
    label: "Cameras",
    icon: Camera,
    roles: [],
  },
  {
    href: "/recordings",
    label: "Recordings",
    icon: Film,
    roles: [],
  },
  {
    href: "/motion",
    label: "Motion Events",
    icon: Activity,
    roles: [],
  },
  {
    href: "/alerts",
    label: "Alerts",
    icon: Bell,
    roles: [],
  },
  {
    href: "/users",
    label: "Users",
    icon: Users,
    roles: ["sysadmin", "circle_admin", "ba_admin", "cust_admin"],
  },
  {
    href: "/customers",
    label: "Customers",
    icon: Building2,
    roles: ["sysadmin", "circle_admin"],
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    roles: ["sysadmin", "circle_admin", "ba_admin", "cust_admin"],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const userRole = session?.user?.role as UserRole | undefined;

  const visibleItems = NAV_ITEMS.filter(
    (item) => item.roles.length === 0 || (userRole && hasRole(userRole, item.roles)),
  );

  return (
    <aside className="flex h-full w-60 flex-col bg-surface border-r border-surface-border">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-surface-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-white tracking-wide">SARVANETRA</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-widest">BSNL</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2">
        <ul className="space-y-0.5">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-brand-700/20 text-brand-300 border border-brand-700/30"
                      : "text-gray-400 hover:bg-surface-elevated hover:text-gray-200",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      isActive ? "text-brand-400" : "text-gray-500",
                    )}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User info */}
      {session?.user && (
        <div className="border-t border-surface-border px-4 py-3">
          <p className="text-xs font-medium text-gray-300 truncate">
            {session.user.name}
          </p>
          <p className="text-[11px] text-gray-500 truncate">
            {getRoleLabel(session.user.role as UserRole)}
          </p>
        </div>
      )}
    </aside>
  );
}