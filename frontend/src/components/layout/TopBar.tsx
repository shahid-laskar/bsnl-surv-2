// src/components/layout/TopBar.tsx
"use client";

import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { Bell, Wifi, WifiOff, LogOut, ChevronDown, AlertTriangle } from "lucide-react";
import { useAlertStore } from "@/stores/alertStore";
import { getRoleLabel, cn } from "@/lib/utils";
import type { UserRole } from "@/types/api";
import {authApi} from "@/lib/api";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const { data: session } = useSession();
  const { unreadCount, isConnected } = useAlertStore();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleSignOut = async () => {
    await signOut({ callbackUrl: "/login" });
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-surface-border bg-surface-card px-6">
      {/* Page title */}
      <h1 className="text-base font-semibold text-gray-100">{title}</h1>

      <div className="flex items-center gap-3">
        {/* WebSocket status indicator */}
        <div
          className={cn(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            isConnected
              ? "bg-status-online/10 text-status-online"
              : "bg-status-offline/10 text-status-offline",
          )}
          title={isConnected ? "Live alerts connected" : "Live alerts disconnected"}
        >
          {isConnected ? (
            <Wifi className="h-3 w-3" />
          ) : (
            <WifiOff className="h-3 w-3" />
          )}
          <span className="hidden sm:inline">{isConnected ? "Live" : "Offline"}</span>
        </div>

        {/* Alert bell */}
        <a
          href="/alerts"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 hover:bg-surface-elevated hover:text-gray-200 transition-colors"
          aria-label={`${unreadCount} unread alerts`}
        >
          <Bell className="h-4.5 w-4.5" />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-severity-critical text-[10px] font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </a>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm text-gray-300 hover:bg-surface-elevated transition-colors"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
              {session?.user?.name?.[0]?.toUpperCase() ?? "U"}
            </div>
            <span className="hidden md:block max-w-[120px] truncate">
              {session?.user?.name}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
          </button>

          {menuOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 top-10 z-20 w-52 rounded-lg border border-surface-border bg-surface-card py-1 shadow-xl">
                <div className="border-b border-surface-border px-3 py-2">
                  <p className="text-xs font-medium text-gray-200">
                    {session?.user?.name}
                  </p>
                  <p className="text-[11px] text-gray-500">
                    {getRoleLabel(session?.user?.role as UserRole)}
                  </p>
                </div>
                <button
                  onClick={() => void handleSignOut()}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:bg-surface-elevated hover:text-gray-200 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
