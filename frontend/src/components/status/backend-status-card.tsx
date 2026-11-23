import type { BackendHealthState } from "@/types/health";

type BackendStatusCardProps = {
  state: BackendHealthState;
  endpoint: string;
  onRefresh: () => void;
};

const statusStyles = {
  loading: {
    label: "Checking",
    dot: "bg-sky-400",
    text: "text-sky-300",
    surface: "border-sky-400/20 bg-sky-400/5",
  },
  healthy: {
    label: "Connected",
    dot: "bg-emerald-400",
    text: "text-emerald-300",
    surface: "border-emerald-400/20 bg-emerald-400/5",
  },
  error: {
    label: "Unavailable",
    dot: "bg-rose-400",
    text: "text-rose-300",
    surface: "border-rose-400/20 bg-rose-400/5",
  },
} as const;

function formatCheckedAt(checkedAt: string | null): string | null {
  if (!checkedAt) {
    return null;
  }
  const date = new Date(checkedAt);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return `${date.toISOString().slice(11, 19)} UTC`;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-white/5 py-2.5 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-[13px] text-slate-200">{value}</span>
    </div>
  );
}

export function BackendStatusCard({
  state,
  endpoint,
  onRefresh,
}: BackendStatusCardProps) {
  const style = statusStyles[state.status];
  const checkedAt = formatCheckedAt(state.checkedAt);

  return (
    <section
      aria-labelledby="backend-status-title"
      className="rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-2xl shadow-black/20 backdrop-blur sm:p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-slate-500">
            Live connectivity
          </p>
          <h2
            id="backend-status-title"
            className="mt-1.5 text-lg font-semibold tracking-tight text-white"
          >
            Backend API
          </h2>
        </div>
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${style.surface} ${style.text}`}
        >
          <span
            aria-hidden="true"
            className={`size-1.5 rounded-full ${style.dot} ${
              state.status === "loading" ? "animate-pulse" : ""
            }`}
          />
          {style.label}
        </span>
      </div>

      <div
        role="status"
        aria-live="polite"
        aria-busy={state.status === "loading"}
        className="mt-5 min-h-28"
      >
        {state.status === "loading" ? (
          <div className="flex items-center gap-3 rounded-xl border border-white/5 bg-black/20 px-4 py-5">
            <span
              aria-hidden="true"
              className="size-5 animate-spin rounded-full border-2 border-sky-400/30 border-t-sky-400"
            />
            <div>
              <p className="text-sm font-medium text-slate-200">
                Checking the live API
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                Requesting GET /api/v1/health
              </p>
            </div>
          </div>
        ) : null}

        {state.status === "healthy" && state.data ? (
          <div>
            <p className="text-base font-medium text-white">
              The API is responding.
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-400">
              A real health request completed successfully from this browser.
            </p>
            <div className="mt-3">
              <DetailRow label="Service" value={state.data.service} />
              <DetailRow label="Environment" value={state.data.environment} />
              <DetailRow label="API version" value={state.data.version} />
              {checkedAt ? (
                <DetailRow label="Checked" value={checkedAt} />
              ) : null}
            </div>
          </div>
        ) : null}

        {state.status === "error" ? (
          <div>
            <p className="text-base font-medium text-white">
              The API is not reachable.
            </p>
            <p className="mt-1 break-words text-sm leading-6 text-slate-400">
              {state.error ??
                "Start the FastAPI server and refresh this connection check."}
            </p>
            {checkedAt ? (
              <p className="mt-3 font-mono text-[11px] uppercase tracking-wider text-slate-600">
                Last checked {checkedAt}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-white/5 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <code
          title={endpoint}
          className="truncate font-mono text-[11px] text-slate-500"
        >
          {endpoint}
        </code>
        <button
          type="button"
          onClick={onRefresh}
          disabled={state.status === "loading"}
          className="inline-flex shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Check again
        </button>
      </div>
    </section>
  );
}
