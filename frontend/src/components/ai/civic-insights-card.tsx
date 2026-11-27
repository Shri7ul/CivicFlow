"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { getAIInsights, type AIInsights } from "@/lib/api/ai";

export function CivicInsightsCard() {
  const { apiRequest } = useAuth();
  const [data, setData] = useState<AIInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getAIInsights(apiRequest));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load local insights.",
      );
    } finally {
      setLoading(false);
    }
  }, [apiRequest]);

  useEffect(() => {
    // Defer the initial state update out of the effect body (same pattern as
    // the other data loaders in this app).
    const timer = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  return (
    <section className="relative overflow-hidden rounded-3xl border border-emerald-400/15 bg-gradient-to-br from-emerald-400/[0.07] via-slate-900/40 to-slate-950/60 p-6 sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-emerald-400/10 blur-3xl" />
      <div className="relative flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300/80">
            Civic AI assistant
          </p>
          <h2 className="mt-1 text-lg font-semibold text-white">Local insights</h2>
        </div>
        <span className="rounded-full border border-white/10 bg-slate-950/60 px-3 py-1 text-[11px] text-slate-300">
          {data?.available
            ? "Groq AI enabled"
            : "Live data summary"}
        </span>
      </div>

      {loading ? (
        <div className="mt-5 space-y-3" role="status">
          <div className="h-4 w-3/4 animate-pulse rounded bg-white/5" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-white/5" />
        </div>
      ) : error ? (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <p className="text-sm text-rose-200">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-white/5"
          >
            Retry
          </button>
        </div>
      ) : data ? (
        <>
          <p className="mt-5 text-sm leading-6 text-slate-200">{data.summary}</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {data.highlights.map((item) => (
              <li
                key={item}
                className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300"
              >
                {item}
              </li>
            ))}
          </ul>
          <p className="mt-5 border-t border-white/5 pt-4 text-[11px] leading-5 text-slate-500">
            {data.limitations}
          </p>
        </>
      ) : null}
    </section>
  );
}
