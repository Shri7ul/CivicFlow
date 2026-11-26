"use client";

import Link from "next/link";
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
  formatDateTime,
  workerStatusLabel,
} from "@/components/workforce/workforce-ui";
import { ApiError } from "@/lib/api/client";
import { getMyApplication, getMyWorkerProfile } from "@/lib/api/workforce";
import type { WorkerApplication, WorkerProfile } from "@/types/workforce";

const guidance: Record<string, string> = {
  PENDING: "Your application has been submitted and is waiting for an administrator to review it.",
  UNDER_REVIEW: "An administrator is reviewing your application. No action is needed from you yet.",
  APPROVED: "Your worker profile is active. You can open the worker workspace.",
  REJECTED: "This application was not approved. Contact an administrator if you believe this is incorrect.",
  ADDITIONAL_INFORMATION_REQUIRED:
    "The reviewer requested more information. Update your details with an administrator before resubmitting.",
  SUSPENDED: "Your worker access is suspended. Contact an administrator for details.",
};

export function ApplicationStatusView() {
  const { apiRequest } = useAuth();
  const [application, setApplication] = useState<WorkerApplication | null>(null);
  const [worker, setWorker] = useState<WorkerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const record = await getMyApplication(apiRequest);
      setApplication(record);
      if (record.status === "APPROVED" || record.status === "SUSPENDED") {
        try {
          setWorker(await getMyWorkerProfile(apiRequest));
        } catch {
          setWorker(null);
        }
      } else {
        setWorker(null);
      }
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        setApplication(null);
        setWorker(null);
      } else {
        setError(
          cause instanceof Error ? cause.message : "Unable to load your application.",
        );
      }
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

  if (loading) return <LoadingBlock label="Loading your application status…" />;
  if (error) return <ErrorNotice message={error} onRetry={() => void load()} />;

  if (!application) {
    return (
      <Card title="Worker application">
        <EmptyState message="You have not submitted a worker application yet." />
        <Link
          href="/workforce/apply"
          className="mt-4 inline-flex rounded-lg bg-emerald-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
        >
          Apply now
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <Card title="Application status">
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill
            label={applicationStatusLabel[application.status]}
            tone={applicationTone(application.status)}
          />
          <span className="text-xs text-slate-500">
            Submitted {formatDateTime(application.created_at)}
          </span>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          {guidance[application.status]}
        </p>
        {application.review_note ? (
          <div className="mt-4 rounded-lg border border-white/10 bg-black/20 px-4 py-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">
              Reviewer note
            </p>
            <p className="mt-1 text-sm text-slate-200">{application.review_note}</p>
          </div>
        ) : null}
      </Card>

      <Card title="Submitted details">
        <dl className="grid gap-4 sm:grid-cols-2">
          {[
            ["Full name", application.full_name],
            ["Specialization", application.specialization],
            ["Service area", application.service_area],
            ["Contact phone", application.phone],
            ["Email", application.email],
            ["Address", application.address],
            ["Experience", application.experience],
            ["Credentials note", application.credentials_note],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[11px] uppercase tracking-wider text-slate-500">
                {label}
              </dt>
              <dd className="mt-1 text-sm leading-6 text-slate-200">
                {value || "—"}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      {worker ? (
        <Card title="Worker profile">
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill
              label={workerStatusLabel[worker.status]}
              tone={worker.status === "ACTIVE" ? "good" : "bad"}
            />
            <span className="text-xs text-slate-500">
              {worker.specialization} · {worker.service_area}
            </span>
          </div>
          {worker.status === "ACTIVE" ? (
            <Link
              href="/worker"
              className="mt-4 inline-flex rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-400/15"
            >
              Open worker workspace
            </Link>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
