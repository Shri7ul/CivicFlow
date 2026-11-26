"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  Card,
  EmptyState,
  ErrorNotice,
  LoadingBlock,
  StatusPill,
  assignmentStatusLabel,
  assignmentTone,
  formatDateTime,
  shortId,
  workerStatusLabel,
} from "@/components/workforce/workforce-ui";
import { getIncident } from "@/lib/api/incidents";
import {
  assignmentAction,
  getMyWorkerProfile,
  listAssignments,
  recordProgress,
  submitCompletion,
} from "@/lib/api/workforce";
import type { Incident } from "@/types/incidents";
import type { Assignment, WorkerProfile } from "@/types/workforce";

type View = "active" | "history";

const activeStatuses = new Set(["OFFERED", "ACCEPTED", "IN_PROGRESS"]);
const td = "px-3 py-3 text-sm text-slate-300";
const th = "px-3 py-2 text-left text-[11px] uppercase tracking-wider text-slate-500";

export function WorkerWorkspace() {
  const { apiRequest } = useAuth();
  const [profile, setProfile] = useState<WorkerProfile | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [view, setView] = useState<View>("active");
  const [selected, setSelected] = useState<Assignment | null>(null);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [own, list] = await Promise.all([
        getMyWorkerProfile(apiRequest),
        listAssignments(apiRequest, { limit: 100 }),
      ]);
      setProfile(own);
      setAssignments(list.items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load your workspace.");
    } finally {
      setLoading(false);
    }
  }, [apiRequest]);

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

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      if (!active) return;
      setIncident(null);
      if (!selected) return;
      void getIncident(apiRequest, selected.incident_id)
        .then((record) => {
          if (active) setIncident(record);
        })
        .catch(() => {
          if (active) setIncident(null);
        });
    }, 0);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [apiRequest, selected]);

  async function act(action: "accept" | "decline" | "start") {
    if (!selected) return;
    if (action === "decline" && !note.trim()) {
      setError("A reason is required to decline an assignment.");
      return;
    }
    setBusy(action);
    setError(null);
    try {
      await assignmentAction(apiRequest, selected.id, action, note.trim() || undefined);
      setNote("");
      await load();
      setSelected(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function complete() {
    if (!selected || note.trim().length < 3) {
      setError("A completion note of at least 3 characters is required.");
      return;
    }
    setBusy("complete");
    setError(null);
    try {
      await submitCompletion(apiRequest, selected.id, note.trim());
      setNote("");
      await load();
      setSelected(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Completion submission failed.");
    } finally {
      setBusy(null);
    }
  }

  async function progress() {
    if (!selected) return;
    setBusy("progress");
    setError(null);
    try {
      await recordProgress(apiRequest, selected.id, note.trim() || "Progress updated", 50);
      setNote("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Progress update failed.");
    } finally {
      setBusy(null);
    }
  }

  const visible = assignments.filter((item) =>
    view === "active"
      ? activeStatuses.has(item.status)
      : !activeStatuses.has(item.status),
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Worker workspace
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Only assignments made to your approved worker profile are shown.
          </p>
        </div>
        {profile ? (
          <StatusPill
            label={workerStatusLabel[profile.status]}
            tone={profile.status === "ACTIVE" ? "good" : "bad"}
          />
        ) : null}
      </div>

      {error ? <ErrorNotice message={error} onRetry={() => void load()} /> : null}
      {loading ? <LoadingBlock label="Loading assignments…" /> : null}

      {!loading ? (
        <>
          <div className="flex gap-2 border-b border-white/10 pb-3">
            {(["active", "history"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setView(item)}
                aria-current={view === item ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm capitalize transition ${
                  view === item
                    ? "bg-emerald-400/15 text-emerald-200"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {item === "active" ? "My assignments" : "Work history"}
              </button>
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card title={`${view === "active" ? "Active" : "Historic"} assignments (${visible.length})`}>
              {visible.length === 0 ? (
                <EmptyState
                  message={
                    view === "active"
                      ? "You have no active assignments."
                      : "No completed or cancelled assignments yet."
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] border-collapse">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className={th}>Incident</th>
                        <th className={th}>Status</th>
                        <th className={th}>Assigned</th>
                        <th className={th}>Deadline</th>
                        <th className={th}>Detail</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {visible.map((item) => (
                        <tr key={item.id}>
                          <td className={td}>{shortId(item.incident_id)}</td>
                          <td className={td}>
                            <StatusPill
                              label={assignmentStatusLabel[item.status]}
                              tone={assignmentTone(item.status)}
                            />
                          </td>
                          <td className={td}>{formatDateTime(item.created_at)}</td>
                          <td className={td}>{formatDateTime(item.deadline)}</td>
                          <td className={td}>
                            <button
                              type="button"
                              onClick={() => {
                                setSelected(item);
                                setNote("");
                              }}
                              className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-slate-200 transition hover:bg-white/5"
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="Assignment detail">
              {!selected ? (
                <EmptyState message="Select an assignment to view details and take action." />
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-slate-500">Incident</p>
                    <p className="mt-0.5 text-sm font-medium text-white">
                      {incident ? incident.title : shortId(selected.incident_id)}
                    </p>
                  </div>
                  <dl className="space-y-2 text-xs">
                    <div>
                      <dt className="text-slate-500">Category / severity</dt>
                      <dd className="text-slate-200">
                        {incident ? `${incident.category} · ${incident.severity}` : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Location</dt>
                      <dd className="text-slate-200">{incident?.address ?? "—"}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Description</dt>
                      <dd className="leading-5 text-slate-300">
                        {incident?.description ?? "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Assigned</dt>
                      <dd className="text-slate-200">{formatDateTime(selected.created_at)}</dd>
                    </div>
                    {selected.completion_note ? (
                      <div>
                        <dt className="text-slate-500">Completion note</dt>
                        <dd className="text-slate-200">{selected.completion_note}</dd>
                      </div>
                    ) : null}
                    {selected.review_note ? (
                      <div>
                        <dt className="text-slate-500">Reviewer note</dt>
                        <dd className="text-amber-200">{selected.review_note}</dd>
                      </div>
                    ) : null}
                  </dl>
                  {activeStatuses.has(selected.status) ? (
                    <div className="space-y-3 border-t border-white/10 pt-4">
                      <label className="block">
                        <span className="mb-1.5 block text-[11px] uppercase tracking-wider text-slate-500">
                          Work note
                        </span>
                        <textarea
                          value={note}
                          onChange={(event) => setNote(event.target.value)}
                          className="min-h-20 w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                        />
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        {selected.status === "OFFERED" ? (
                          <>
                            <button
                              type="button"
                              disabled={busy !== null}
                              onClick={() => void act("accept")}
                              className="rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
                            >
                              {busy === "accept" ? "Working…" : "Accept"}
                            </button>
                            <button
                              type="button"
                              disabled={busy !== null}
                              onClick={() => void act("decline")}
                              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:bg-white/5 disabled:opacity-50"
                            >
                              {busy === "decline" ? "Working…" : "Decline"}
                            </button>
                          </>
                        ) : null}
                        {selected.status === "ACCEPTED" ? (
                          <button
                            type="button"
                            disabled={busy !== null}
                            onClick={() => void act("start")}
                            className="col-span-2 rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
                          >
                            {busy === "start" ? "Working…" : "Start work"}
                          </button>
                        ) : null}
                        {selected.status === "IN_PROGRESS" ? (
                          <>
                            <button
                              type="button"
                              disabled={busy !== null}
                              onClick={() => void progress()}
                              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:bg-white/5 disabled:opacity-50"
                            >
                              {busy === "progress" ? "Saving…" : "Update progress"}
                            </button>
                            <button
                              type="button"
                              disabled={busy !== null}
                              onClick={() => void complete()}
                              className="rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
                            >
                              {busy === "complete" ? "Submitting…" : "Submit completion"}
                            </button>
                          </>
                        ) : null}
                      </div>
                      <p className="text-[11px] leading-4 text-slate-500">
                        Completion is submitted for administrator verification. It does
                        not resolve the incident by itself.
                      </p>
                    </div>
                  ) : null}
                </div>
              )}
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
