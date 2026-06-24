// src/routes/AppRouter.tsx
// Defines all client-side routes.
// Protected routes require authentication — checked client-side via AuthContext.
// All actual permission enforcement is done server-side by the FastAPI backend.

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CamerasPage } from "@/pages/CamerasPage";
import { CameraAddPage } from "@/pages/CameraAddPage";
import { CameraDetailPage } from "@/pages/CameraDetailPage";
import { RecordingsPage } from "@/pages/RecordingsPage";
import { MotionPage } from "@/pages/MotionPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { UsersPage } from "@/pages/UsersPage";
import { CustomersPage } from "@/pages/CustomersPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { Loader2 } from "lucide-react";

// ── Protected route wrapper ───────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-surface">
        <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// ── Router ────────────────────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected dashboard routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="cameras" element={<CamerasPage />} />        
        <Route path="cameras/add" element={<CameraAddPage />} />
        <Route path="cameras/:id" element={<CameraDetailPage />} />
        <Route path="recordings" element={<RecordingsPage />} />
        <Route path="motion" element={<MotionPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}