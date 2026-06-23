// src/pages/CustomersPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { customerApi } from "@/lib/api";
import { Building2, Plus, Loader2 } from "lucide-react";
import { RoleGuard } from "@/components/layout/RoleGuard";

export function CustomersPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["customers", page],
    queryFn: () => customerApi.list({ page, page_size: 25 }).then((r) => r.data),
  });

  const customers = data?.items ?? [];

  return (
    <RoleGuard
      roles={["sysadmin", "circle_admin", "ba_admin"]}
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-gray-400">
          You don&apos;t have permission to manage customers.
        </div>
      }
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Customers</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {data?.total ?? 0} customers registered
            </p>
          </div>
          <RoleGuard roles={["sysadmin", "circle_admin", "ba_admin"]}>
            <button className="flex items-center gap-2 rounded-lg bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 transition-colors">
              <Plus className="h-4 w-4" />
              Add Customer
            </button>
          </RoleGuard>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
          </div>
        ) : customers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Building2 className="h-10 w-10 text-gray-600 mb-3" />
            <p className="text-sm text-gray-300">No customers found</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-surface-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface-elevated">
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Company</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Circle / BA</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Plan</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Cameras</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {customers.map((customer) => (
                  <tr key={customer.id} className="hover:bg-surface-elevated transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-200">{customer.com_name}</p>
                      <p className="text-[11px] text-gray-500 truncate max-w-xs">{customer.com_adr}</p>
                      {customer.gstn && (
                        <p className="text-[11px] text-gray-500 mt-0.5">GST: {customer.gstn}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-300">{customer.cir_name}</p>
                      <p className="text-xs text-gray-500">{customer.ba_name}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      <span className="rounded-full bg-brand-700/10 px-2 py-0.5 text-xs font-medium text-brand-400">
                        {customer.plan_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 bg-surface-border rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-brand-500" 
                            style={{ width: `${Math.min(100, (customer.camera_count / customer.camera_limit) * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">
                          {customer.camera_count} / {customer.camera_limit}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

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
    </RoleGuard>
  );
}
