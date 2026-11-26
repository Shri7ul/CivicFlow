"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { listDepartments } from "@/lib/api/incidents";
import { submitWorkerApplication } from "@/lib/api/workforce";
import { ErrorNotice } from "@/components/workforce/workforce-ui";
import type { Department } from "@/types/incidents";
import type { ApplicationPayload } from "@/types/workforce";

const inputClass =
  "w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50";
const labelClass =
  "mb-1.5 block text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400";

export function ApplicationForm() {
  const { apiRequest, profile } = useAuth();
  const router = useRouter();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form, setForm] = useState<ApplicationPayload>({
    full_name: profile?.full_name ?? "",
    phone: profile?.phone ?? "",
    email: "",
    specialization: "",
    department_id: "",
    service_area: "",
    address: "",
    experience: "",
    credentials_note: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void listDepartments(apiRequest)
      .then((rows) => {
        if (active) setDepartments(rows);
      })
      .catch(() => {
        // The department list is optional on the application form.
      });
    return () => {
      active = false;
    };
  }, [apiRequest]);

  function set(field: keyof ApplicationPayload, value: string) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!form.full_name.trim() || !form.specialization.trim() || !form.service_area.trim()) {
      setError("Full name, specialization and service area are required.");
      return;
    }
    setBusy(true);
    try {
      const payload: ApplicationPayload = {
        full_name: form.full_name.trim(),
        specialization: form.specialization.trim(),
        service_area: form.service_area.trim(),
      };
      for (const field of [
        "phone",
        "email",
        "address",
        "experience",
        "credentials_note",
      ] as const) {
        const value = form[field]?.trim();
        if (value) payload[field] = value;
      }
      if (form.department_id) payload.department_id = form.department_id;
      await submitWorkerApplication(apiRequest, payload);
      router.push("/workforce/status");
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to submit the application.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-2xl border border-white/10 bg-slate-900/50 p-6"
    >
      <h1 className="text-2xl font-semibold tracking-tight text-white">
        Apply as a field worker
      </h1>
      <p className="mt-2 text-sm leading-6 text-slate-400">
        Your application is reviewed by an administrator. You will not receive
        operational access until it is explicitly approved.
      </p>

      {error ? (
        <div className="mt-5">
          <ErrorNotice message={error} />
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <label>
          <span className={labelClass}>Full name</span>
          <input
            className={inputClass}
            value={form.full_name}
            onChange={(event) => set("full_name", event.target.value)}
            required
          />
        </label>
        <label>
          <span className={labelClass}>Contact phone</span>
          <input
            className={inputClass}
            value={form.phone ?? ""}
            onChange={(event) => set("phone", event.target.value)}
            placeholder="+880..."
          />
        </label>
        <label>
          <span className={labelClass}>Email</span>
          <input
            type="email"
            className={inputClass}
            value={form.email ?? ""}
            onChange={(event) => set("email", event.target.value)}
          />
        </label>
        <label>
          <span className={labelClass}>Specialization</span>
          <input
            className={inputClass}
            value={form.specialization}
            onChange={(event) => set("specialization", event.target.value)}
            placeholder="Drainage, Roads, Sanitation..."
            required
          />
        </label>
        <label>
          <span className={labelClass}>Department (optional)</span>
          <select
            className={inputClass}
            value={form.department_id ?? ""}
            onChange={(event) => set("department_id", event.target.value)}
          >
            <option value="">Not specified</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className={labelClass}>Service area</span>
          <input
            className={inputClass}
            value={form.service_area}
            onChange={(event) => set("service_area", event.target.value)}
            placeholder="Ward or neighborhood you can serve"
            required
          />
        </label>
        <label className="sm:col-span-2">
          <span className={labelClass}>Address</span>
          <input
            className={inputClass}
            value={form.address ?? ""}
            onChange={(event) => set("address", event.target.value)}
          />
        </label>
        <label className="sm:col-span-2">
          <span className={labelClass}>Relevant experience</span>
          <textarea
            className={`${inputClass} min-h-24 resize-y`}
            value={form.experience ?? ""}
            onChange={(event) => set("experience", event.target.value)}
          />
        </label>
        <label className="sm:col-span-2">
          <span className={labelClass}>Credentials note</span>
          <textarea
            className={`${inputClass} min-h-20 resize-y`}
            value={form.credentials_note ?? ""}
            onChange={(event) => set("credentials_note", event.target.value)}
            placeholder="Describe credentials or supporting documents. Do not paste secrets."
          />
        </label>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-emerald-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Submitting…" : "Submit application"}
        </button>
        <span className="text-xs text-slate-500">
          One application per account. Decisions are recorded in the audit log.
        </span>
      </div>
    </form>
  );
}
