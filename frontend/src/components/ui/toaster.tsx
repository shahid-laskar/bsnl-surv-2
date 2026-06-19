// src/components/ui/toaster.tsx
// Minimal toast implementation that doesn't need shadcn CLI setup.
// Upgrade to full shadcn/ui toast later once CLI is run.

"use client";

import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { X, CheckCircle, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within Toaster");
  return ctx;
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => removeToast(id), 4000);
  }, [removeToast]);

  // Expose globally for use outside React tree
  useEffect(() => {
    (window as typeof window & { __toast?: (m: string, t?: ToastType) => void }).__toast = addToast;
  }, [addToast]);

  const icons: Record<ToastType, React.ElementType> = {
    success: CheckCircle,
    error: AlertTriangle,
    info: Info,
  };

  const colours: Record<ToastType, string> = {
    success: "border-status-online/30 bg-status-online/10 text-status-online",
    error: "border-severity-critical/30 bg-severity-critical/10 text-severity-critical",
    info: "border-brand-700/30 bg-brand-700/10 text-brand-400",
  };

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => {
        const Icon = icons[t.type];
        return (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-2 rounded-lg border px-3 py-2.5 shadow-lg animate-fade-in",
              colours[t.type],
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="text-sm">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="ml-2 opacity-60 hover:opacity-100 transition-opacity"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// Convenience function for use outside components
export function showToast(message: string, type: ToastType = "info") {
  const fn = (window as typeof window & { __toast?: (m: string, t?: ToastType) => void }).__toast;
  if (fn) fn(message, type);
}
