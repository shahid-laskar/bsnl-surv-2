// src/app/(dashboard)/users/page.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/api";
import { getRoleLabel, formatDate, cn } from "@/lib/utils";
import { Users, Plus, Loader2, UserX, CheckCircle } from "lucide-react";
import { RoleGuard } from "@/components/layout/RoleGuard";

export default function UsersPage() {
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["users", page],
    queryFn: () => userApi.list({ page, page_size: 25 }).then((r) => r.data),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => userApi.deactivate(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const users = data?.items ?? [];

  return (
    <RoleGuard
      roles={["sysadmin", "circle_admin", "ba_admin", "cust_admin"]}
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-gray-400">
          You don&apos;t have permission to manage users.
        </div>
      }
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Users</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {data?.total ?? 0} users registered
            </p>
          </div>
          <RoleGuard roles={["sysadmin", "circle_admin", "ba_admin", "cust_admin"]}>
            <button className="flex items-center gap-2 rounded-lg bg-brand-700 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 transition-colors">
              <Plus className="h-4 w-4" />
              Add User
            </button>
          </RoleGuard>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-brand-400" />
          </div>
        ) : users.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Users className="h-10 w-10 text-gray-600 mb-3" />
            <p className="text-sm text-gray-300">No users found</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-surface-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface-elevated">
                  <th className="px-4 py-3 text-left font-medium text-gray-400">User</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Role</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Organisation</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Joined</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-400">Status</th>
                  <th className="w-16 px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-surface-elevated transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-200">
                        {user.first_name} {user.last_name}
                      </p>
                      <p className="text-[11px] text-gray-500">{user.username}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-brand-700/10 px-2 py-0.5 text-xs font-medium text-brand-400">
                        {getRoleLabel(user.role)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {user.com_name ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDate(user.date_joined)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
                          user.is_active
                            ? "bg-status-online/10 text-status-online"
                            : "bg-status-offline/10 text-status-offline",
                        )}
                      >
                        {user.is_active ? (
                          <CheckCircle className="h-3 w-3" />
                        ) : (
                          <UserX className="h-3 w-3" />
                        )}
                        {user.is_active ? "Active" : "Deactivated"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {user.is_active && (
                        <button
                          onClick={() => deactivateMutation.mutate(user.id)}
                          disabled={deactivateMutation.isPending}
                          className="text-xs text-gray-500 hover:text-severity-critical transition-colors"
                          title="Deactivate user"
                        >
                          Deactivate
                        </button>
                      )}
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
