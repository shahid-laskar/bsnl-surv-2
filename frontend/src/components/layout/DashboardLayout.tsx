// src/components/layout/DashboardLayout.tsx
// Client-side layout replacing the Next.js server component (dashboard)/layout.tsx.
// Auth check is done in ProtectedRoute — by the time this renders, the user is authenticated.

import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { AlertSocketProvider } from "./AlertSocketProvider";

export function DashboardLayout() {
  return (
    <AlertSocketProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar title="Sarvanetra" />
          <main className="flex-1 overflow-y-auto bg-surface p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </AlertSocketProvider>
  );
}
