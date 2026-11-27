"use client";

import type { WorkforceNotification } from "@/types/workforce";

type Props = {
  items: WorkforceNotification[];
  unread: number;
  loading: boolean;
  error: string | null;
  busyId: string | null;
  onMarkRead: (id: string) => void;
};

export function InboxPanel({
  items,
  unread,
  loading,
  error,
  busyId,
  onMarkRead,
}: Props) {
  return (
    <section
      aria-labelledby="inbox-heading"
      className="rounded-3xl border border-white/10 bg-white/[0.03] p-5 sm:p-6"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="inbox-heading" className="text-sm font-semibold text-white">
          Notifications
        </h2>
        <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-300">
          {loading ? "Loading…" : `${unread} unread`}
        </span>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-rose-300/20 bg-rose-300/5 px-3 py-2 text-xs text-rose-100">
          {error}
        </p>
      ) : null}

      {!loading && items.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-white/10 px-3 py-5 text-center text-xs text-slate-500">
          No notifications yet. Status changes for your reports will appear
          here when staff publish them.
        </p>
      ) : null}

      <ul className="mt-4 space-y-3">
        {items.slice(0, 6).map((item) => (
          <li
            key={item.id}
            className="rounded-xl border border-white/10 bg-slate-950/40 p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-slate-100">{item.title}</p>
              {item.read_at ? (
                <span className="text-[10px] text-slate-500">Read</span>
              ) : null}
            </div>
            <p className="mt-1 text-[11px] leading-4 text-slate-400">
              {item.body}
            </p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-[10px] text-slate-500">
                {new Date(item.created_at).toLocaleString()}
              </span>
              {!item.read_at ? (
                <button
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => onMarkRead(item.id)}
                  className="rounded-md border border-white/15 px-2 py-1 text-[10px] text-slate-200 transition hover:bg-white/5 disabled:opacity-50"
                >
                  {busyId === item.id ? "Saving…" : "Mark read"}
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
