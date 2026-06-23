// src/pages/SettingsPage.tsx
import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { authApi } from "@/lib/api";
import { getRoleLabel } from "@/lib/utils";
import { User, KeyRound, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

export function SettingsPage() {
  const { session } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  if (!session?.user) return null;

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setStatus({ type: "error", message: "New passwords do not match" });
      return;
    }
    if (newPassword.length < 8) {
      setStatus({ type: "error", message: "Password must be at least 8 characters" });
      return;
    }

    setIsSubmitting(true);
    setStatus(null);

    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setStatus({ type: "success", message: "Password updated successfully" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setStatus({ 
        type: "error", 
        message: err?.response?.data?.error?.message || "Failed to change password" 
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Settings</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Manage your account preferences and security
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="rounded-lg border border-surface-border bg-surface-elevated p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-brand-700/10 rounded-lg">
              <User className="h-5 w-5 text-brand-400" />
            </div>
            <h3 className="text-base font-medium text-gray-200">Profile Information</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-500">Name</label>
              <p className="text-sm font-medium text-gray-200 mt-1">{session.user.name}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Email address</label>
              <p className="text-sm font-medium text-gray-200 mt-1">{session.user.email}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Role</label>
              <p className="mt-1">
                <span className="rounded-full bg-brand-700/10 px-2 py-0.5 text-xs font-medium text-brand-400">
                  {getRoleLabel(session.user.role)}
                </span>
              </p>
            </div>
          </div>
        </div>

        {/* Change Password Card */}
        <div className="rounded-lg border border-surface-border bg-surface-elevated p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-brand-700/10 rounded-lg">
              <KeyRound className="h-5 w-5 text-brand-400" />
            </div>
            <h3 className="text-base font-medium text-gray-200">Change Password</h3>
          </div>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {status && (
              <div className={`p-3 rounded-md flex items-start gap-2 text-sm ${
                status.type === "success" 
                  ? "bg-status-online/10 text-status-online" 
                  : "bg-severity-critical/10 text-severity-critical"
              }`}>
                {status.type === "success" ? (
                  <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                )}
                <span>{status.message}</span>
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Current Password</label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-md border border-surface-border bg-surface-background px-3 py-2 text-sm text-gray-200 outline-none focus:border-brand-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">New Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-md border border-surface-border bg-surface-background px-3 py-2 text-sm text-gray-200 outline-none focus:border-brand-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Confirm New Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-md border border-surface-border bg-surface-background px-3 py-2 text-sm text-gray-200 outline-none focus:border-brand-500 transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-md bg-brand-700 py-2 text-sm font-medium text-white hover:bg-brand-600 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update Password"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
