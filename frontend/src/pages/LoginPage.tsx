// src/pages/LoginPage.tsx
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoginSchema, type LoginFormValues } from "@/types/schemas";
import { ShieldCheck, Eye, EyeOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  // Redirect to where the user was trying to go, or "/"
  const from = (location.state as { from?: string })?.from ?? "/";

  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(LoginSchema),
  });

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null);
    try {
      await login(values.username, values.password);
      navigate(from, { replace: true });
    } catch {
      setServerError("Invalid username or password");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-700 shadow-lg shadow-brand-900/50">
            <ShieldCheck className="h-8 w-8 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold tracking-wide text-white">SARVANETRA</h1>
            <p className="text-xs text-gray-500 uppercase tracking-widest mt-0.5">
              BSNL Surveillance Platform
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-surface-border bg-surface-card p-6 shadow-xl">
          <h2 className="mb-5 text-sm font-semibold text-gray-300">Sign in to continue</h2>

          {/* Server error */}
          {serverError && (
            <div className="mb-4 rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-3 py-2.5">
              <p className="text-xs text-severity-critical">{serverError}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {/* Username */}
            <div>
              <label
                htmlFor="username"
                className="mb-1.5 block text-xs font-medium text-gray-400"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                autoFocus
                {...register("username")}
                className={cn(
                  "w-full rounded-lg border bg-surface px-3 py-2.5 text-sm text-gray-100 placeholder-gray-600",
                  "transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                  errors.username
                    ? "border-severity-critical/50"
                    : "border-surface-border focus:border-brand-700/50",
                )}
                placeholder="Enter your username"
              />
              {errors.username && (
                <p className="mt-1 text-xs text-severity-critical">
                  {errors.username.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-xs font-medium text-gray-400"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  {...register("password")}
                  className={cn(
                    "w-full rounded-lg border bg-surface px-3 py-2.5 pr-10 text-sm text-gray-100 placeholder-gray-600",
                    "transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                    errors.password
                      ? "border-severity-critical/50"
                      : "border-surface-border focus:border-brand-700/50",
                  )}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-severity-critical">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-[11px] text-gray-600">
          BSNL Kerala · IT Cell · Secure access only
        </p>
      </div>
    </div>
  );
}
