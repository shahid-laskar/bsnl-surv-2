// src/app/(dashboard)/alerts/page.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { alertApi } from "@/lib/api";
import { AlertList } from "@/components/alerts/AlertList";
import { Loader2, Bell } from "lucide-react";

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState<"" | "up" | "down">("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", statusFilter, page],
    queryFn: () =>
      alertApi
        .list({
          status: statusFilter || undefined,
          page,
          page_size: 50,
        })
        .then((r) => r.data),
    refetchInterval: 15_000,
  });

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Alerts</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {data?.total ?? 0} total · auto-refreshes every 15s
          </p>
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1 rounded-lg border border-surface-border bg-surface-elevated p-1">
          {(
            [
              { value: "", label: "All" },
              { value: "down", label: "Offline" },
              { value: "up", label: "Online" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setStatusFilter(tab.value); setPage(1); }}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === tab.value
                  ? "bg-brand-700 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="rounded-lg border border-surface-border bg-surface-card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
          </div>
        ) : (
          <AlertList alerts={data?.items ?? []} />
        )}
      </div>

      {/* Pagination */}
      {(data?.pages ?? 1) > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            className="rounded-md border border-surface-border px-3 py-1.5 text-xs text-gray-400 hover:bg-surface-elevated disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {data?.pages}
          </span>
          <button
            disabled={page === (data?.pages ?? 1)}
            onClick={() => setPage(page + 1)}
            className="rounded-md border border-surface-border px-3 py-1.5 text-xs text-gray-400 hover:bg-surface-elevated disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
