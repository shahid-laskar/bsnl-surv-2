import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Loader2, UserPlus } from "lucide-react";
import { userApi, geographyApi } from "@/lib/api";
import type { UserCreateRequest, UserRole } from "@/types/api";

interface AddUserModalProps {
  onClose: () => void;
}

const ROLES: { value: UserRole; label: string }[] = [
  { value: "sysadmin", label: "System Admin" },
  { value: "circle_admin", label: "Circle Admin" },
  { value: "ba_admin", label: "BA Admin" },
  { value: "cust_admin", label: "Customer Admin" },
  { value: "viewer", label: "Viewer" },
];

export function AddUserModal({ onClose }: AddUserModalProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<UserCreateRequest>({
    username: "",
    password: "",
    first_name: "",
    last_name: "",
    email: "",
    role: "viewer",
  });

  // Queries
  const { data: circles } = useQuery({
    queryKey: ["circles"],
    queryFn: () => geographyApi.listCircles().then((r) => r.data),
  });

  const { data: bas, isLoading: isLoadingBAs } = useQuery({
    queryKey: ["bas", formData.cir_id],
    queryFn: () => geographyApi.listBAs(formData.cir_id!).then((r) => r.data),
    enabled: !!formData.cir_id,
  });

  const { data: customers, isLoading: isLoadingCustomers } = useQuery({
    queryKey: ["customers-by-ba", formData.ba_id],
    queryFn: () => geographyApi.listCustomersByBA(formData.ba_id!).then((r) => r.data),
    enabled: !!formData.ba_id,
  });

  // Conditions
  const needsCircle = formData.role !== "sysadmin";
  const needsBA = ["ba_admin", "cust_admin", "viewer"].includes(formData.role);
  const needsCustomer = ["cust_admin", "viewer"].includes(formData.role);

  const createMutation = useMutation({
    mutationFn: (data: UserCreateRequest) => userApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: ["cir_id", "ba_id", "com_id"].includes(name) ? parseInt(value) || undefined : value,
    }));
  };

  const handleRoleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const role = e.target.value as UserRole;
    setFormData(prev => ({
      ...prev,
      role,
      cir_id: role === "sysadmin" ? undefined : prev.cir_id,
      ba_id: ["sysadmin", "circle_admin"].includes(role) ? undefined : prev.ba_id,
      com_id: ["sysadmin", "circle_admin", "ba_admin"].includes(role) ? undefined : prev.com_id,
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-xl border border-surface-border bg-surface-card shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-surface-border bg-surface px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700/20 text-brand-400">
              <UserPlus className="h-4 w-4" />
            </div>
            <h3 className="font-semibold text-gray-100">Add User</h3>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="rounded-lg p-1.5 text-gray-400 hover:bg-surface-elevated hover:text-gray-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">First Name *</label>
              <input
                required
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                placeholder="John"
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Last Name *</label>
              <input
                required
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Doe"
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">Email Address *</label>
            <input
              required
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="john@example.com"
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Username *</label>
              <input
                required
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="johndoe"
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Password *</label>
              <input
                required
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">Role *</label>
            <select
              required
              name="role"
              value={formData.role}
              onChange={handleRoleChange}
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            >
              {ROLES.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          {needsCircle && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Circle *</label>
              <select
                required
                name="cir_id"
                value={formData.cir_id || ""}
                onChange={(e) => {
                  handleChange(e);
                  setFormData(prev => ({ ...prev, ba_id: undefined, com_id: undefined }));
                }}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              >
                <option value="" disabled>Select Circle</option>
                {(circles ?? []).map(c => (
                  <option key={c.id} value={c.id}>{c.cir_name}</option>
                ))}
              </select>
            </div>
          )}

          {needsBA && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Business Area *</label>
              <select
                required
                name="ba_id"
                value={formData.ba_id || ""}
                onChange={(e) => {
                  handleChange(e);
                  setFormData(prev => ({ ...prev, com_id: undefined }));
                }}
                disabled={!formData.cir_id || isLoadingBAs}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 disabled:opacity-50 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              >
                <option value="" disabled>Select BA</option>
                {(bas ?? []).map(b => (
                  <option key={b.id} value={b.id}>{b.ba_name}</option>
                ))}
              </select>
            </div>
          )}

          {needsCustomer && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Customer *</label>
              <select
                required
                name="com_id"
                value={formData.com_id || ""}
                onChange={handleChange}
                disabled={!formData.ba_id || isLoadingCustomers}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 disabled:opacity-50 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              >
                <option value="" disabled>Select Customer</option>
                {(customers ?? []).map(c => (
                  <option key={c.id} value={c.id}>{c.com_name}</option>
                ))}
              </select>
            </div>
          )}

          {createMutation.isError && (
            <p className="text-xs text-severity-critical">
              {createMutation.error instanceof Error ? createMutation.error.message : "Failed to create user"}
            </p>
          )}

          <div className="mt-2 flex justify-end gap-3 border-t border-surface-border pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm font-medium text-gray-400 hover:text-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex items-center gap-2 rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Create User
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
