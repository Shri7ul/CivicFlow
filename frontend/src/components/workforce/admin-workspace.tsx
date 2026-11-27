"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  Card,
  EmptyState,
  ErrorNotice,
  LoadingBlock,
  StatusPill,
  applicationStatusLabel,
  applicationTone,
  assignmentStatusLabel,
  assignmentTone,
  formatDateTime,
  shortId,
  workerStatusLabel,
} from "@/components/workforce/workforce-ui";
import {
  assignIncident,
  listAssignments,
  listAuditEvents,
  listCandidates,
  listWorkerApplications,
  listWorkers,
  markNotificationRead,
  listNotifications,
  reviewWorkerApplication,
  setWorkerStatus,
  assignmentAction,
  getAdminOverview,
  verifyCompletion,
} from "@/lib/api/workforce";
import {
  changeIncidentStatus,
  listIncidents,
} from "@/lib/api/incidents";
import type { Incident } from "@/types/incidents";
import type {
  AdminOverview,
  Assignment,
  WorkerApplication,
  WorkerProfile,
  WorkerStatus,
  WorkforceEventRecord,
  WorkforceNotification,
} from "@/types/workforce";

type Tab =
  | "overview"
  | "incidents"
  | "applications"
  | "workers"
  | "assignments"
  | "audit";

const tabs: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "incidents", label: "Incident review" },
  { id: "applications", label: "Worker applications" },
  { id: "workers", label: "Workers" },
  { id: "assignments", label: "Assignments" },
  { id: "audit", label: "Audit log" },
];

const th = "px-3 py-2 text-left text-[11px] uppercase tracking-wider text-slate-500";
const td = "px-3 py-3 text-sm text-slate-300";

export function AdminWorkspace() {
  const { apiRequest } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [applications, setApplications] = useState<WorkerApplication[]>([]);
  const [workers, setWorkers] = useState<WorkerProfile[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [events, setEvents] = useState<WorkforceEventRecord[]>([]);
  const [notices, setNotices] = useState<WorkforceNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkerApplication | null>(null);
  const [note, setNote] = useState("");
  const [workerFilter, setWorkerFilter] = useState<WorkerStatus | "">("");
  const [assignmentFilter, setAssignmentFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "overview") {
        const [counts, inbox] = await Promise.all([
          getAdminOverview(apiRequest),
          listNotifications(apiRequest),
        ]);
        setOverview(counts);
        setNotices(inbox.items);
      } else if (tab === "incidents") {
        const result = await listIncidents(apiRequest, { pageSize: 100 });
        setIncidents(result.items);
      } else if (tab === "applications") {
        setApplications((await listWorkerApplications(apiRequest, { limit: 100 })).items);
      } else if (tab === "workers") {
        setWorkers(
          (await listWorkers(apiRequest, { status: workerFilter || undefined, limit: 100 })).items,
        );
      } else if (tab === "assignments") {
        setAssignments((await listAssignments(apiRequest, { limit: 100 })).items);
      } else {
        setEvents((await listAuditEvents(apiRequest)).items);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load workspace data.");
    } finally {
      setLoading(false);
    }
  }, [apiRequest, tab, workerFilter]);

  useEffect(() => {
    let disposed = false;
    const timer = setTimeout(() => {
      if (!disposed) void load();
    }, 0);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [load]);

  async function review(decision: "APPROVE" | "REJECT" | "REQUEST_INFO" | "UNDER_REVIEW") {
    if (!selected) return;
    if ((decision === "REJECT" || decision === "REQUEST_INFO") && !note.trim()) {
      setError("A review note is required for this decision.");
      return;
    }
    setBusy(decision);
    setError(null);
    try {
      await reviewWorkerApplication(apiRequest, selected.id, decision, note.trim() || undefined);
      setSelected(null);
      setNote("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Review action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function changeWorkerStatus(worker: WorkerProfile, action: "suspend" | "reactivate") {
    if (action === "suspend" && !note.trim()) {
      setError("A reason is required to suspend a worker.");
      return;
    }
    setBusy(`${action}-${worker.id}`);
    setError(null);
    try {
      await setWorkerStatus(apiRequest, worker.id, action, note.trim() || undefined);
      setNote("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Worker status change failed.");
    } finally {
      setBusy(null);
    }
  }

  async function cancelAssignment(assignment: Assignment) {
    if (!note.trim()) {
      setError("A reason is required to cancel an assignment.");
      return;
    }
    setBusy(`cancel-${assignment.id}`);
    setError(null);
    try {
      await assignmentAction(apiRequest, assignment.id, "cancel", note.trim());
      setNote("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cancellation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function assignFromCandidates(incidentId: string) {
    setBusy(`candidates-${incidentId}`);
    setError(null);
    try {
      const result = await listCandidates(apiRequest, incidentId);
      const eligible = result.items.find((item) => item.eligible);
      if (!eligible) {
        setError("No eligible worker is available for this incident.");
        return;
      }
      await assignIncident(apiRequest, {
        incidentId,
        workerProfileId: eligible.worker_profile_id,
        note: `Admin-selected candidate: ${eligible.rationale}`,
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Assignment failed.");
    } finally {
      setBusy(null);
    }
  }

  async function verifyIncident(incident: Incident) {
    setBusy(`verify-${incident.id}`);
    setError(null);
    try {
      await changeIncidentStatus(apiRequest, incident.id, {
        status: "VERIFIED",
        note: "Admin verification for field assignment",
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Verification failed.");
    } finally {
      setBusy(null);
    }
  }

  async function verifyWork(assignment: Assignment, approve: boolean) {
    setBusy(`verify-work-${assignment.id}`);
    setError(null);
    try {
      await verifyCompletion(
        apiRequest,
        assignment.id,
        approve,
        note.trim() || undefined,
      );
      setNote("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Completion verification failed.");
    } finally {
      setBusy(null);
    }
  }

  const overviewCards: { label: string; value: number }[] = overview
    ? [
        { label: "Total incidents", value: overview.total_incidents },
        { label: "Unreviewed", value: overview.unreviewed_incidents },
        { label: "Awaiting assignment", value: overview.verified_awaiting_assignment },
        { label: "Assigned", value: overview.assigned_incidents },
        { label: "In progress", value: overview.in_progress_incidents },
        { label: "Awaiting verification", value: overview.awaiting_verification },
        { label: "Verified completed", value: overview.verified_completed },
        { label: "Resolved", value: overview.resolved_incidents },
        { label: "Pending applications", value: overview.pending_applications },
        { label: "Active workers", value: overview.active_workers },
        { label: "Suspended workers", value: overview.suspended_workers },
      ]
    : [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Admin operations
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Application review, workforce management and incident assignment.
          All figures come from the live API; no actions are simulated.
        </p>
      </div>

      <nav
        aria-label="Admin sections"
        className="flex flex-wrap gap-2 border-b border-white/10 pb-3"
      >
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            aria-current={tab === item.id ? "page" : undefined}
            className={`rounded-lg px-3 py-2 text-sm transition ${
              tab === item.id
                ? "bg-emerald-400/15 text-emerald-200"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {error ? <ErrorNotice message={error} onRetry={() => void load()} /> : null}
      {loading ? <LoadingBlock label="Loading workspace data…" /> : null}

      {!loading && tab === "overview" ? (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {overviewCards.map((card) => (
              <div
                key={card.label}
                className="rounded-xl border border-white/10 bg-slate-900/50 p-4"
              >
                <p className="text-[11px] uppercase tracking-wider text-slate-500">
                  {card.label}
                </p>
                <p className="mt-2 text-2xl font-semibold text-white">{card.value}</p>
              </div>
            ))}
          </div>
          <Card title="Unread notifications">
            {notices.filter((item) => !item.read_at).length === 0 ? (
              <EmptyState message="No unread notifications." />
            ) : (
              <ul className="divide-y divide-white/5">
                {notices
                  .filter((item) => !item.read_at)
                  .map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-white">{item.title}</p>
                        <p className="text-xs text-slate-400">{item.body}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          void markNotificationRead(apiRequest, item.id).then(load);
                        }}
                        className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-slate-300 transition hover:bg-white/5"
                      >
                        Mark read
                      </button>
                    </li>
                  ))}
              </ul>
            )}
          </Card>
        </div>
      ) : null}

      {!loading && tab === "incidents" ? (
        <Card title={`Incidents (${incidents.length})`}>
          <p className="mb-4 text-xs text-slate-400">
            Verify an Open report before assignment, then assign the best
            eligible worker. Verification is recorded in the incident history.
          </p>
          {incidents.length === 0 ? (
            <EmptyState message="No incidents have been reported yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className={th}>Incident</th>
                    <th className={th}>Category</th>
                    <th className={th}>Severity</th>
                    <th className={th}>Status</th>
                    <th className={th}>Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {incidents.map((incident) => (
                    <tr key={incident.id}>
                      <td className={td}>
                        <span className="block text-white">{incident.title}</span>
                        <span className="text-xs text-slate-500">
                          {shortId(incident.id)}
                        </span>
                      </td>
                      <td className={td}>{incident.category}</td>
                      <td className={td}>{incident.severity}</td>
                      <td className={td}>{incident.status}</td>
                      <td className={td}>
                        {incident.status === "OPEN" ? (
                          <button
                            type="button"
                            disabled={busy !== null}
                            onClick={() => void verifyIncident(incident)}
                            className="rounded-md border border-emerald-400/30 px-2 py-1.5 text-xs text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-50"
                          >
                            Verify
                          </button>
                        ) : incident.status === "VERIFIED" ? (
                          <button
                            type="button"
                            disabled={busy !== null}
                            onClick={() => void assignFromCandidates(incident.id)}
                            className="rounded-md border border-emerald-400/30 px-2 py-1.5 text-xs text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-50"
                          >
                            Assign best candidate
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}

      {!loading && tab === "applications" ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card title={`Applications (${applications.length})`}>
            {applications.length === 0 ? (
              <EmptyState message="No worker applications submitted yet." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className={th}>Applicant</th>
                      <th className={th}>Specialization</th>
                      <th className={th}>Service area</th>
                      <th className={th}>Status</th>
                      <th className={th}>Submitted</th>
                      <th className={th}>Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {applications.map((item) => (
                      <tr key={item.id}>
                        <td className={td}>{item.full_name}</td>
                        <td className={td}>{item.specialization}</td>
                        <td className={td}>{item.service_area}</td>
                        <td className={td}>
                          <StatusPill
                            label={applicationStatusLabel[item.status]}
                            tone={applicationTone(item.status)}
                          />
                        </td>
                        <td className={td}>{formatDateTime(item.created_at)}</td>
                        <td className={td}>
                          <button
                            type="button"
                            onClick={() => {
                              setSelected(item);
                              setNote(item.review_note ?? "");
                            }}
                            className="rounded-md border border-emerald-400/30 px-2.5 py-1.5 text-xs text-emerald-200 transition hover:bg-emerald-400/10"
                          >
                            Review
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Review panel">
            {!selected ? (
              <EmptyState message="Select an application to review its details." />
            ) : (
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-white">{selected.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {selected.specialization} · {selected.service_area}
                  </p>
                </div>
                <dl className="space-y-2 text-xs">
                  <div>
                    <dt className="text-slate-500">Experience</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {selected.experience || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Credentials note</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {selected.credentials_note || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Contact</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {selected.phone || selected.email || "—"}
                    </dd>
                  </div>
                </dl>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] uppercase tracking-wider text-slate-500">
                    Review note
                  </span>
                  <textarea
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    className="min-h-20 w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(["APPROVE", "REJECT", "REQUEST_INFO", "UNDER_REVIEW"] as const).map(
                    (decision) => (
                      <button
                        key={decision}
                        type="button"
                        disabled={busy !== null}
                        onClick={() => void review(decision)}
                        className="rounded-lg border border-white/10 px-2 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/5 disabled:opacity-50"
                      >
                        {busy === decision ? "Working…" : applicationStatusLabel[decision === "REQUEST_INFO" ? "ADDITIONAL_INFORMATION_REQUIRED" : decision === "UNDER_REVIEW" ? "UNDER_REVIEW" : decision === "APPROVE" ? "APPROVED" : "REJECTED"]}
                      </button>
                    ),
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      ) : null}

      {!loading && tab === "workers" ? (
        <Card title={`Workers (${workers.length})`}>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <label className="text-xs text-slate-400">
              Status
              <select
                value={workerFilter}
                onChange={(event) => setWorkerFilter(event.target.value as WorkerStatus | "")}
                className="ml-2 rounded-md border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
              >
                <option value="">All</option>
                <option value="ACTIVE">Active</option>
                <option value="SUSPENDED">Suspended</option>
              </select>
            </label>
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Reason for suspension"
              className="min-w-52 flex-1 rounded-md border border-white/10 bg-slate-950 px-3 py-1.5 text-sm text-white"
            />
          </div>
          {workers.length === 0 ? (
            <EmptyState message="No workers match this filter." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className={th}>Worker</th>
                    <th className={th}>Specialization</th>
                    <th className={th}>Service area</th>
                    <th className={th}>Assignments</th>
                    <th className={th}>Status</th>
                    <th className={th}>Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {workers.map((worker) => (
                    <tr key={worker.id}>
                      <td className={td}>{worker.full_name ?? shortId(worker.profile_id)}</td>
                      <td className={td}>{worker.specialization}</td>
                      <td className={td}>{worker.service_area}</td>
                      <td className={td}>
                        {worker.active_assignments} active / {worker.total_assignments} total
                      </td>
                      <td className={td}>
                        <StatusPill
                          label={workerStatusLabel[worker.status]}
                          tone={worker.status === "ACTIVE" ? "good" : "bad"}
                        />
                      </td>
                      <td className={td}>
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() =>
                            void changeWorkerStatus(
                              worker,
                              worker.status === "ACTIVE" ? "suspend" : "reactivate",
                            )
                          }
                          className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-slate-200 transition hover:bg-white/5 disabled:opacity-50"
                        >
                          {worker.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}

      {!loading && tab === "assignments" ? (
        <Card title={`Assignments (${assignments.length})`}>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <input
              value={assignmentFilter}
              onChange={(event) => setAssignmentFilter(event.target.value)}
              placeholder="Incident id"
              className="min-w-52 flex-1 rounded-md border border-white/10 bg-slate-950 px-3 py-1.5 text-sm text-white"
            />
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Cancellation reason"
              className="min-w-52 flex-1 rounded-md border border-white/10 bg-slate-950 px-3 py-1.5 text-sm text-white"
            />
          </div>
          {assignments.length === 0 ? (
            <EmptyState message="No assignments recorded yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] border-collapse">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className={th}>Incident</th>
                    <th className={th}>Worker</th>
                    <th className={th}>Status</th>
                    <th className={th}>Rationale</th>
                    <th className={th}>Created</th>
                    <th className={th}>Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {assignments
                    .filter((item) =>
                      assignmentFilter
                        ? item.incident_id.startsWith(assignmentFilter.trim())
                        : true,
                    )
                    .map((item) => (
                      <tr key={item.id}>
                        <td className={td}>{shortId(item.incident_id)}</td>
                        <td className={td}>{shortId(item.worker_profile_id)}</td>
                        <td className={td}>
                          <StatusPill
                            label={assignmentStatusLabel[item.status]}
                            tone={assignmentTone(item.status)}
                          />
                        </td>
                        <td className={`${td} text-xs`}>{item.rationale ?? "—"}</td>
                        <td className={td}>{formatDateTime(item.created_at)}</td>
                        <td className={td}>
                          {item.status === "OFFERED" ? (
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={busy !== null}
                                onClick={() => void assignFromCandidates(item.incident_id)}
                                className="rounded-md border border-emerald-400/30 px-2 py-1.5 text-xs text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-50"
                              >
                                Assign best candidate
                              </button>
                              <button
                                type="button"
                                disabled={busy !== null}
                                onClick={() => void cancelAssignment(item)}
                                className="rounded-md border border-white/10 px-2 py-1.5 text-xs text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : item.status === "COMPLETION_SUBMITTED" ? (
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={busy !== null}
                                onClick={() => void verifyWork(item, true)}
                                className="rounded-md border border-emerald-400/30 px-2 py-1.5 text-xs text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-50"
                              >
                                Verify completion
                              </button>
                              <button
                                type="button"
                                disabled={busy !== null}
                                onClick={() => void verifyWork(item, false)}
                                className="rounded-md border border-white/10 px-2 py-1.5 text-xs text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
                              >
                                Reject
                              </button>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}

      {!loading && tab === "audit" ? (
        <Card title={`Audit events (${events.length})`}>
          {events.length === 0 ? (
            <EmptyState message="No workforce audit events recorded." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className={th}>Action</th>
                    <th className={th}>Entity</th>
                    <th className={th}>Previous</th>
                    <th className={th}>New</th>
                    <th className={th}>Actor</th>
                    <th className={th}>Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {events.map((item) => (
                    <tr key={item.id}>
                      <td className={td}>{item.action}</td>
                      <td className={td}>
                        {item.entity_type} · {shortId(item.entity_id)}
                      </td>
                      <td className={td}>{item.previous_state ?? "—"}</td>
                      <td className={td}>{item.new_state ?? "—"}</td>
                      <td className={td}>
                        {item.actor_id ? shortId(item.actor_id) : "system"}
                      </td>
                      <td className={td}>{formatDateTime(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}
    </div>
  );
}
