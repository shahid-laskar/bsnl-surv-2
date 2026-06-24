
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cameraApi, customerApi, deviceApi } from "@/lib/api";
import type { CameraCreateRequest, Device } from "@/types/api";
import { CameraCreateSchema } from "@/types/schemas";
import { RoleGuard } from "@/components/layout/RoleGuard";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";

interface CameraFormState {
  cam_name: string;
  cam_loc: string;
  cam_make: string;
  cam_usrname: string;
  cam_pass: string;
  cam_strm1: string;
  cam_strm2: string;
  cam_strm3: string;
  cam_onvif: string; // kept as string in form state, parsed to number | undefined on submit
  motion_active: boolean;
  com_id: string;
  device_id: string;
  strm_type_id: string;
}

const initialState: CameraFormState = {
  cam_name: "",
  cam_loc: "",
  cam_make: "",
  cam_usrname: "",
  cam_pass: "",
  cam_strm1: "",
  cam_strm2: "",
  cam_strm3: "",
  cam_onvif: "",
  motion_active: false,
  com_id: "",
  device_id: "",
  strm_type_id: "",
};

export function CameraAddPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CameraFormState>(initialState);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: customersData, isLoading: customersLoading } = useQuery({
    queryKey: ["customers", "all-for-form"],
    queryFn: () => customerApi.list({ page: 1, page_size: 200 }).then((r) => r.data),
  });

  const { data: devicesData, isLoading: devicesLoading } = useQuery({
    queryKey: ["devices", "all-for-form"],
    queryFn: () =>
      deviceApi.list().then((r) => {
        const raw = r.data as unknown;
        return Array.isArray(raw) ? raw : (raw as { items: Device[] })?.items ?? [];
      }),
  });

  const { data: streamTypesData, isLoading: streamTypesLoading } = useQuery({
    queryKey: ["devices", "stream-types"],
    queryFn: () => deviceApi.streamTypes().then((r) => r.data),
  });

  const createCamera = useMutation({
    mutationFn: (data: CameraCreateRequest) => cameraApi.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      navigate(`/cameras/${response.data.cam_id}`);
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
          ?.error?.message ?? "Failed to create camera. Check the form and try again.";
      setFormError(message);
    },
  });

  function update<K extends keyof CameraFormState>(key: K, value: CameraFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    // Build the candidate payload, then validate it with the same
    // CameraCreateSchema other forms in this codebase use (schemas.ts).
    const candidate = {
      cam_name: form.cam_name.trim(),
      cam_loc: form.cam_loc.trim(),
      cam_make: form.cam_make.trim(),
      cam_usrname: form.cam_usrname.trim(),
      cam_pass: form.cam_pass,
      cam_strm1: form.cam_strm1.trim(),
      cam_strm2: form.cam_strm2.trim() || undefined,
      cam_strm3: form.cam_strm3.trim() || undefined,
      cam_onvif: form.cam_onvif.trim() ? Number(form.cam_onvif) : undefined,
      motion_active: form.motion_active,
      com_id: form.com_id ? Number(form.com_id) : undefined,
      device_id: form.device_id ? Number(form.device_id) : undefined,
      strm_type_id: form.strm_type_id ? Number(form.strm_type_id) : undefined,
      is_active: true,
    };

    const result = CameraCreateSchema.safeParse(candidate);
    if (!result.success) {
      setFormError(result.error.issues[0]?.message ?? "Please check the form and try again.");
      return;
    }

    createCamera.mutate(result.data);
  }

  const customers = customersData?.items ?? [];
  const devices = devicesData ?? [];
  const streamTypes = streamTypesData ?? [];
  const referenceDataLoading = customersLoading || devicesLoading || streamTypesLoading;

  return (
    <RoleGuard
      roles={["sysadmin", "circle_admin"]}
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-gray-400">
          You don&apos;t have permission to add cameras.
        </div>
      }
    >
      <div className="flex flex-col gap-5 max-w-2xl">
        <Link
          to="/cameras"
          className="flex w-fit items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All cameras
        </Link>

        <div>
          <h2 className="text-lg font-semibold text-gray-100">Add Camera</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Registers the camera and its stream path with MediaMTX.
          </p>
        </div>

        {referenceDataLoading ? (
          <div className="flex items-center gap-2 py-10 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading form data…
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="flex flex-col gap-4 rounded-lg border border-surface-border bg-surface-card p-5"
          >
            {formError && (
              <div className="flex items-start gap-2 rounded-md border border-severity-warning/30 bg-severity-warning/10 px-3 py-2 text-xs text-severity-warning">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                {formError}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <Field label="Camera name" required>
                <input
                  className={inputClass}
                  value={form.cam_name}
                  onChange={(e) => update("cam_name", e.target.value)}
                  placeholder="Gate Camera 1"
                />
              </Field>
              <Field label="Location" required>
                <input
                  className={inputClass}
                  value={form.cam_loc}
                  onChange={(e) => update("cam_loc", e.target.value)}
                  placeholder="Main Entrance"
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Make / manufacturer" required>
                <input
                  className={inputClass}
                  value={form.cam_make}
                  onChange={(e) => update("cam_make", e.target.value)}
                  placeholder="Matrix"
                />
              </Field>
              <Field label="ONVIF port" hint="Leave blank if the camera doesn't support ONVIF">
                <input
                  className={inputClass}
                  type="number"
                  value={form.cam_onvif}
                  onChange={(e) => update("cam_onvif", e.target.value)}
                  placeholder="80"
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Camera username" required>
                <input
                  className={inputClass}
                  value={form.cam_usrname}
                  onChange={(e) => update("cam_usrname", e.target.value)}
                  placeholder="admin"
                />
              </Field>
              <Field label="Camera password" required>
                <input
                  className={inputClass}
                  type="password"
                  value={form.cam_pass}
                  onChange={(e) => update("cam_pass", e.target.value)}
                />
              </Field>
            </div>

            <Field
              label="Primary stream URL"
              required
              hint="Must start with rtsp:// or rtmp://"
            >
              <input
                className={inputClass}
                value={form.cam_strm1}
                onChange={(e) => update("cam_strm1", e.target.value)}
                placeholder="rtsp://admin:password@10.44.0.219:554/unicaststream/1"
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Secondary stream URL" hint="Optional">
                <input
                  className={inputClass}
                  value={form.cam_strm2}
                  onChange={(e) => update("cam_strm2", e.target.value)}
                />
              </Field>
              <Field label="Tertiary stream URL" hint="Optional">
                <input
                  className={inputClass}
                  value={form.cam_strm3}
                  onChange={(e) => update("cam_strm3", e.target.value)}
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Customer" required>
                <select
                  className={inputClass}
                  value={form.com_id}
                  onChange={(e) => update("com_id", e.target.value)}
                >
                  <option value="">Select customer…</option>
                  {customers.map((c: { id: number; com_name: string }) => (
                    <option key={c.id} value={c.id}>
                      {c.com_name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Device" required>
                <select
                  className={inputClass}
                  value={form.device_id}
                  onChange={(e) => update("device_id", e.target.value)}
                >
                  <option value="">Select device…</option>
                  {devices.map((d: { id: number; device_id: string; dev_name: string | null }) => (
                    <option key={d.id} value={d.id}>
                      {d.dev_name ?? d.device_id}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Stream type" required hint="RTSP, RTMP, or RTSP CLOUD">
              <select
                className={inputClass}
                value={form.strm_type_id}
                onChange={(e) => update("strm_type_id", e.target.value)}
              >
                <option value="">Select stream type…</option>
                {streamTypes.map((s: { id: number; strm_type: string }) => (
                  <option key={s.id} value={s.id}>
                    {s.strm_type}
                  </option>
                ))}
              </select>
            </Field>

            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={form.motion_active}
                onChange={(e) => update("motion_active", e.target.checked)}
                className="h-4 w-4 rounded border-surface-border bg-surface-elevated"
              />
              Enable motion detection (requires ONVIF port above)
            </label>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={createCamera.isPending}
                className="flex items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {createCamera.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {createCamera.isPending ? "Creating…" : "Create camera"}
              </button>
              <Link
                to="/cameras"
                className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </Link>
            </div>
          </form>
        )}
      </div>
    </RoleGuard>
  );
}

// ── Small field wrapper, local to this file ──────────────────────────────
function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-gray-400">
        {label}
        {required && <span className="text-severity-warning"> *</span>}
      </span>
      {children}
      {hint && <span className="text-[11px] text-gray-500">{hint}</span>}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-surface-border bg-surface-elevated px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-brand-700/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-colors";

