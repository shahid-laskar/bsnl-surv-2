import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Loader2, Building2 } from "lucide-react";
import { customerApi, geographyApi, planApi } from "@/lib/api";
import type { CustomerCreateRequest } from "@/types/api";

interface AddCustomerModalProps {
  onClose: () => void;
}

export function AddCustomerModal({ onClose }: AddCustomerModalProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Partial<CustomerCreateRequest>>({
    com_name: "",
    com_adr: "",
    gstn: "",
    cir_id: 0,
    ba_id: 0,
    plan_id: 0,
  });

  const { data: circles } = useQuery({
    queryKey: ["circles"],
    queryFn: () => geographyApi.listCircles().then((r) => r.data),
  });

  const { data: bas, isLoading: isLoadingBAs } = useQuery({
    queryKey: ["bas", formData.cir_id],
    queryFn: () => geographyApi.listBAs(formData.cir_id!).then((r) => r.data),
    enabled: !!formData.cir_id && formData.cir_id > 0,
  });

  const { data: plans } = useQuery({
    queryKey: ["plans"],
    queryFn: () => planApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: CustomerCreateRequest) => customerApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.com_name || !formData.com_adr || !formData.cir_id || !formData.ba_id || !formData.plan_id) return;
    createMutation.mutate(formData as CustomerCreateRequest);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: ["cir_id", "ba_id", "plan_id"].includes(name) ? parseInt(value) || 0 : value,
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md overflow-hidden rounded-xl border border-surface-border bg-surface-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-surface-border bg-surface px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700/20 text-brand-400">
              <Building2 className="h-4 w-4" />
            </div>
            <h3 className="font-semibold text-gray-100">Add Customer</h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-surface-elevated hover:text-gray-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">Company Name *</label>
            <input
              required
              name="com_name"
              value={formData.com_name}
              onChange={handleChange}
              placeholder="e.g. Acme Corp"
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">Company Address *</label>
            <input
              required
              name="com_adr"
              value={formData.com_adr}
              onChange={handleChange}
              placeholder="Full address"
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">GSTN</label>
            <input
              name="gstn"
              value={formData.gstn}
              onChange={handleChange}
              placeholder="Optional GST number"
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Circle *</label>
              <select
                required
                name="cir_id"
                value={formData.cir_id || ""}
                onChange={(e) => {
                  handleChange(e);
                  setFormData(prev => ({ ...prev, ba_id: 0 }));
                }}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              >
                <option value="" disabled>Select Circle</option>
                {(circles ?? []).map(c => (
                  <option key={c.id} value={c.id}>{c.cir_name}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300">Business Area *</label>
              <select
                required
                name="ba_id"
                value={formData.ba_id || ""}
                onChange={handleChange}
                disabled={!formData.cir_id || isLoadingBAs}
                className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 disabled:opacity-50 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
              >
                <option value="" disabled>Select BA</option>
                {(bas ?? []).map(b => (
                  <option key={b.id} value={b.id}>{b.ba_name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300">Plan *</label>
            <select
              required
              name="plan_id"
              value={formData.plan_id || ""}
              onChange={handleChange}
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all"
            >
              <option value="" disabled>Select Plan</option>
              {(plans ?? []).map(p => (
                <option key={p.id} value={p.id}>{p.plan_name} ({p.cam_limit} cameras)</option>
              ))}
            </select>
          </div>

          {createMutation.isError && (
            <p className="text-xs text-severity-critical">
              {createMutation.error instanceof Error ? createMutation.error.message : "Failed to create customer"}
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
              Create Customer
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
