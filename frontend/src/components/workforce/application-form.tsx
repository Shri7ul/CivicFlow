"use client";

import Link from "next/link";
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

const STEPS = [
  { title: "Identity & contact", hint: "How an administrator can reach you" },
  { title: "Skills & service area", hint: "What you can do and where" },
  { title: "Review & submit", hint: "Confirm before it enters the review queue" },
] as const;

const STATUS_GUIDE = [
  { label: "Pending", detail: "Submitted, waiting for an administrator." },
  { label: "Approved", detail: "Role becomes Field worker and your worker profile is active." },
  { label: "Rejected", detail: "Not approved. The reviewer's note explains why." },
] as const;

export function ApplicationForm() {
  const { apiRequest, profile } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
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

  function next() {
    setError(null);
    if (step === 0 && !form.full_name.trim()) {
      setError("Full name is required.");
      return;
    }
    if (step === 1 && (!form.specialization.trim() || !form.service_area.trim())) {
      setError("Specialization and service area are required.");
      return;
    }
    setStep((value) => Math.min(value + 1, STEPS.length - 1));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!form.full_name.trim() || !form.specialization.trim() || !form.service_area.trim()) {
      setError("Full name, specialization and service area are required.");
      setStep(0);
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
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Apply as a field worker
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Three short steps. An administrator reviews every submission; operational
          access starts only after an explicit approval.
        </p>

        <ol className="mt-6 grid gap-2 sm:grid-cols-3">
          {STEPS.map((item, index) => (
            <li
              key={item.title}
              aria-current={index === step ? "step" : undefined}
              className={`rounded-xl border px-3 py-3 ${
                index === step
                  ? "border-emerald-400/30 bg-emerald-400/10"
                  : "border-white/10 bg-white/[0.02]"
              }`}
            >
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                Step {index + 1} of {STEPS.length}
              </p>
              <p className="mt-1 text-sm font-medium text-white">{item.title}</p>
              <p className="mt-0.5 text-xs text-slate-400">{item.hint}</p>
            </li>
          ))}
        </ol>

        {error ? (
          <div className="mt-5">
            <ErrorNotice message={error} />
          </div>
        ) : null}

        {step === 0 ? (
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
              <span className={labelClass}>Address</span>
              <input
                className={inputClass}
                value={form.address ?? ""}
                onChange={(event) => set("address", event.target.value)}
              />
            </label>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
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
            <label className="sm:col-span-2">
              <span className={labelClass}>Service area (ward / zone)</span>
              <input
                className={inputClass}
                value={form.service_area}
                onChange={(event) => set("service_area", event.target.value)}
                placeholder="Ward or neighborhood you can serve"
                required
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
        ) : null}

        {step === 2 ? (
          <dl className="mt-6 grid gap-x-6 gap-y-3 rounded-xl border border-white/10 bg-slate-950/40 p-5 sm:grid-cols-2">
            {[
              ["Full name", form.full_name],
              ["Contact", form.phone || form.email || "—"],
              ["Specialization", form.specialization],
              ["Service area", form.service_area],
              ["Experience", form.experience || "—"],
              ["Credentials", form.credentials_note || "—"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-[11px] uppercase tracking-wider text-slate-500">
                  {label}
                </dt>
                <dd className="mt-1 break-words text-sm text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          {step > 0 ? (
            <button
              type="button"
              onClick={() => {
                setError(null);
                setStep((value) => value - 1);
              }}
              className="rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/5"
            >
              Back
            </button>
          ) : null}
          {step < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={next}
              className="rounded-lg bg-emerald-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
            >
              Continue
            </button>
          ) : (
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-emerald-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? "Submitting…" : "Submit application"}
            </button>
          )}
          <span className="text-xs text-slate-500">
            One application per account. Decisions are recorded in the audit log.
          </span>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-white">What happens next</h2>
          <Link href="/workforce/status" className="text-xs text-emerald-300 hover:text-emerald-200">
            Track my application
          </Link>
        </div>
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          {STATUS_GUIDE.map((item) => (
            <div key={item.label} className="rounded-lg border border-white/5 bg-slate-950/40 p-3">
              <dt className="text-xs font-medium text-slate-200">{item.label}</dt>
              <dd className="mt-1 text-xs leading-5 text-slate-400">{item.detail}</dd>
            </div>
          ))}
        </dl>
      </div>
    </form>
  );
}
