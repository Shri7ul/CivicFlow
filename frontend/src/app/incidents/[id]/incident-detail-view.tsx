"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { EvidenceGallery } from "@/components/incidents/evidence-gallery";
import { SeverityBadge, StatusBadge } from "@/components/incidents/status-badge";
import {
  changeIncidentStatus,
  getIncident,
  listDepartments,
  updateIncident,
} from "@/lib/api/incidents";
import {
  allowedNextStatuses,
  categories,
  categoryLabels,
  formatCoordinates,
  formatDateTime,
  severities,
  severityLabels,
  statusLabels,
} from "@/lib/incidents";
import type {
  Department,
  Incident,
  IncidentCategory,
  IncidentSeverity,
  IncidentStatus,
} from "@/types/incidents";

const inputClass =
  "mt-1.5 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3.5 py-2.5 text-sm text-white outline-none transition focus:border-emerald-400/50";
const labelClass =
  "text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400";

const actionLabels: Record<IncidentStatus, string> = {
  OPEN: "Reopen",
  ACKNOWLEDGED: "Acknowledge",
  IN_PROGRESS: "Start work",
  RESOLVED: "Mark resolved",
  CLOSED: "Close incident",
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load incident.";
}

export function IncidentDetailView({ incidentId }: { incidentId: string }) {
  const { profile, apiRequest } = useAuth();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentId, setDepartmentId] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCategory, setEditCategory] =
    useState<IncidentCategory>("DRAINAGE");
  const [editSeverity, setEditSeverity] = useState<IncidentSeverity>("MEDIUM");
  const [editAddress, setEditAddress] = useState("");

  const isStaff = profile?.role === "WORKER" || profile?.role === "ADMIN";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getIncident(apiRequest, incidentId);
      const nextDepartments = isStaff
        ? await listDepartments(apiRequest)
        : [];
      setIncident(next);
      setDepartments(nextDepartments);
      setDepartmentId(
        next.assigned_department?.id ?? nextDepartments[0]?.id ?? "",
      );
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [apiRequest, incidentId, isStaff]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function beginEdit() {
    if (!incident) return;
    setEditTitle(incident.title);
    setEditDescription(incident.description);
    setEditCategory(incident.category);
    setEditSeverity(incident.severity);
    setEditAddress(incident.address ?? "");
    setEditError(null);
    setEditing(true);
  }

  async function saveEdit() {
    if (!incident) return;
    setSaving(true);
    setEditError(null);
    try {
      const next = await updateIncident(apiRequest, incident.id, {
        title: editTitle.trim(),
        description: editDescription.trim(),
        category: editCategory,
        severity: editSeverity,
        address: editAddress.trim() || null,
      });
      setIncident(next);
      setEditing(false);
    } catch (saveError) {
      setEditError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function advance(target: IncidentStatus) {
    if (!incident) return;
    setSaving(true);
    setError(null);
    try {
      const next = await changeIncidentStatus(apiRequest, incident.id, {
        status: target,
        department_id: departmentId || null,
        note: note.trim() || null,
      });
      setIncident(next);
      setNote("");
    } catch (statusError) {
      setError(errorMessage(statusError));
    } finally {
      setSaving(false);
    }
  }

  if (loading && !incident) {
    return (
      <main className="mx-auto w-full max-w-5xl px-5 py-12 sm:px-8">
        <div className="h-72 animate-pulse rounded-3xl border border-white/5 bg-white/[0.03]" />
      </main>
    );
  }

  if (!incident) {
    return (
      <main className="mx-auto w-full max-w-5xl px-5 py-12 sm:px-8">
        <div className="rounded-3xl border border-rose-300/20 bg-rose-300/5 p-8">
          <h1 className="text-lg font-semibold text-white">
            Incident unavailable
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            {error ?? "This incident does not exist or is not visible to you."}
          </p>
          <Link
            href="/incidents"
            className="mt-5 inline-flex rounded-lg border border-white/15 px-4 py-2 text-sm text-white"
          >
            Back to incidents
          </Link>
        </div>
      </main>
    );
  }

  const canEdit = isStaff
    ? incident.status !== "CLOSED"
    : incident.status === "OPEN" && incident.reporter.id === profile?.id;
  const canUploadEvidence =
    isStaff || incident.reporter.id === profile?.id;
  const nextStatuses = isStaff ? allowedNextStatuses(incident.status) : [];

  return (
    <main className="mx-auto w-full max-w-5xl px-5 py-12 sm:px-8">
      <Link
        href="/incidents"
        className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 transition hover:text-slate-300"
      >
        ← Back to incidents
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={incident.status} />
            <SeverityBadge severity={incident.severity} />
            <span className="inline-flex rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-semibold text-slate-300">
              {categoryLabels[incident.category]}
            </span>
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            {incident.title}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Reported by {incident.reporter.full_name} ·{" "}
            {formatDateTime(incident.created_at)}
          </p>
        </div>
        {canEdit ? (
          <button
            type="button"
            onClick={beginEdit}
            className="rounded-xl border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:border-white/25"
          >
            Edit report
          </button>
        ) : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl border border-rose-300/20 bg-rose-300/5 px-4 py-3 text-sm text-rose-100"
        >
          {error}
        </p>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.45fr_0.55fr]">
        <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
          {editing ? (
            <div className="space-y-4">
              <div>
                <label htmlFor="edit-title" className={labelClass}>
                  Title
                </label>
                <input
                  id="edit-title"
                  value={editTitle}
                  onChange={(event) => setEditTitle(event.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="edit-description" className={labelClass}>
                  Description
                </label>
                <textarea
                  id="edit-description"
                  rows={5}
                  value={editDescription}
                  onChange={(event) => setEditDescription(event.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="edit-category" className={labelClass}>
                    Category
                  </label>
                  <select
                    id="edit-category"
                    value={editCategory}
                    onChange={(event) =>
                      setEditCategory(event.target.value as IncidentCategory)
                    }
                    className={inputClass}
                  >
                    {categories.map((value) => (
                      <option key={value} value={value}>
                        {categoryLabels[value]}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="edit-severity" className={labelClass}>
                    Severity
                  </label>
                  <select
                    id="edit-severity"
                    value={editSeverity}
                    onChange={(event) =>
                      setEditSeverity(event.target.value as IncidentSeverity)
                    }
                    className={inputClass}
                  >
                    {severities.map((value) => (
                      <option key={value} value={value}>
                        {severityLabels[value]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="edit-address" className={labelClass}>
                  Address
                </label>
                <input
                  id="edit-address"
                  value={editAddress}
                  onChange={(event) => setEditAddress(event.target.value)}
                  className={inputClass}
                />
              </div>
              {editError ? (
                <p className="text-sm text-rose-200">{editError}</p>
              ) : null}
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveEdit()}
                  className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save changes"}
                </button>
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="rounded-lg border border-white/15 px-4 py-2 text-sm text-white"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <h2 className="text-sm font-semibold text-white">Description</h2>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-300">
                {incident.description}
              </p>
            </>
          )}

          <dl className="mt-8 grid gap-4 border-t border-white/10 pt-6 sm:grid-cols-2">
            <div>
              <dt className={labelClass}>Location</dt>
              <dd className="mt-1 text-sm text-slate-300">
                {incident.address ?? "Pinned location"}
              </dd>
              <dd className="mt-1 font-mono text-xs text-slate-500">
                {formatCoordinates(incident.latitude, incident.longitude)}
              </dd>
            </div>
            <div>
              <dt className={labelClass}>Assigned department</dt>
              <dd className="mt-1 text-sm text-slate-300">
                {incident.assigned_department?.name ?? "Not assigned"}
              </dd>
            </div>
            <div>
              <dt className={labelClass}>Last updated</dt>
              <dd className="mt-1 text-sm text-slate-300">
                {formatDateTime(incident.updated_at)}
              </dd>
            </div>
            <div>
              <dt className={labelClass}>Resolved</dt>
              <dd className="mt-1 text-sm text-slate-300">
                {incident.resolved_at
                  ? formatDateTime(incident.resolved_at)
                  : "Not yet"}
              </dd>
            </div>
          </dl>
        </section>

        <aside className="space-y-6">
          {isStaff ? (
            <section className="rounded-3xl border border-emerald-400/20 bg-emerald-400/[0.04] p-6">
              <h2 className="text-sm font-semibold text-white">
                Response actions
              </h2>
              {nextStatuses.length === 0 ? (
                <p className="mt-3 text-sm text-slate-400">
                  This incident is closed.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  <div>
                    <label htmlFor="department" className={labelClass}>
                      Department
                    </label>
                    <select
                      id="department"
                      value={departmentId}
                      onChange={(event) => setDepartmentId(event.target.value)}
                      className={inputClass}
                    >
                      <option value="">Select a department</option>
                      {departments.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="status-note" className={labelClass}>
                      Note (optional)
                    </label>
                    <input
                      id="status-note"
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Crew dispatched, site inspected…"
                      className={inputClass}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    {nextStatuses.map((target) => (
                      <button
                        key={target}
                        type="button"
                        disabled={saving}
                        onClick={() => void advance(target)}
                        className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
                      >
                        {actionLabels[target]} → {statusLabels[target]}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </section>
          ) : null}

          <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <h2 className="text-sm font-semibold text-white">History</h2>
            <ol className="mt-4 space-y-4">
              {incident.history.map((event, index) => (
                <li key={event.id} className="flex gap-3">
                  <span
                    className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-400"
                    aria-hidden="true"
                  />
                  <div>
                    <p className="text-sm font-medium text-slate-200">
                      {event.from_status
                        ? `${statusLabels[event.from_status]} → ${statusLabels[event.to_status]}`
                        : statusLabels[event.to_status]}
                    </p>
                    {event.note ? (
                      <p className="mt-0.5 text-xs leading-5 text-slate-400">
                        {event.note}
                      </p>
                    ) : null}
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {event.actor?.full_name ?? "System"} ·{" "}
                      {formatDateTime(event.created_at)}
                    </p>
                  </div>
                  {index === incident.history.length - 1 ? null : (
                    <span className="sr-only">, </span>
                  )}
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>

      <EvidenceGallery
        incidentId={incident.id}
        evidence={incident.evidence ?? []}
        canUpload={canUploadEvidence}
        onUploaded={(uploaded) => {
          setIncident((current) =>
            current
              ? { ...current, evidence: [...(current.evidence ?? []), ...uploaded] }
              : current,
          );
        }}
      />
    </main>
  );
}
