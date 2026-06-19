// src/app/(dashboard)/layout.tsx
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { AlertSocketProvider } from "@/components/layout/AlertSocketProvider";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

// Server component — auth check happens here
export default async function DashboardLayout({ children }: DashboardLayoutProps) {
  const session = await auth();

  if (!session) {
    redirect("/login");
  }

  return (
    <AlertSocketProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar title="Sarvanetra" />
          <main className="flex-1 overflow-y-auto bg-surface p-6">{children}</main>
        </div>
      </div>
    </AlertSocketProvider>
  );
}
