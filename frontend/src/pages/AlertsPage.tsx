// src/pages/AlertsPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { alertApi } from "@/lib/api";
import { AlertList } from "@/components/alerts/AlertList";
import { Loader2 } from "lucide-react";

export function AlertsPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", page],
    queryFn: () =>
      alertApi
        .list({
          skip: (page - 1) * 50,
          limit: 50,
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
      {Math.ceil((data?.total ?? 0) / 50) > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            className="rounded-md border border-surface-border px-3 py-1.5 text-xs text-gray-400 hover:bg-surface-elevated disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {Math.ceil((data?.total ?? 0) / 50)}
          </span>
          <button
            disabled={page === Math.ceil((data?.total ?? 0) / 50)}
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
