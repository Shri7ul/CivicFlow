"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { navigationForRole, roleLabel } from "@/lib/auth/routing";

const NAV_ITEMS = [
  { path: "/incidents", label: "Incidents" },
  { path: "/map", label: "Map" },
  { path: "/risk", label: "Risk" },
  { path: "/decisions", label: "Decisions" },
  { path: "/operations", label: "Operations" },
  { path: "/validation", label: "Validation" },
  { path: "/pilot", label: "Pilot" },
  { path: "/dashboard", label: "Dashboard" },
] as const;

export function AuthNav({ compact = false }: { compact?: boolean }) {
  const { status, profile, signOut } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);

  if (status === "loading") {
    return (
      <span
        aria-label="Loading account"
        className="inline-block h-8 w-20 animate-pulse rounded-lg bg-white/5"
      />
    );
  }

  if (status === "authenticated" && profile) {
    return (
      <div className="flex items-center gap-2">
        {!compact ? (
          <span className="hidden text-right text-[11px] leading-4 text-slate-400 lg:block">
            <span className="block font-medium text-slate-200">
              {profile.full_name}
            </span>
            {roleLabel(profile.role)}
          </span>
        ) : null}
        {NAV_ITEMS.filter((item) =>
          navigationForRole(profile.role).includes(item.path),
        ).map((item) =>
          item.path === "/dashboard" ? (
            <Link
              key={item.path}
              href={item.path}
              className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-2 text-xs font-medium text-emerald-200 transition hover:bg-emerald-400/15 sm:px-3 sm:text-sm"
            >
              {item.label}
            </Link>
          ) : (
            <Link
              key={item.path}
              href={item.path}
              className="rounded-lg px-2.5 py-2 text-xs font-medium text-slate-300 transition hover:text-white sm:text-sm"
            >
              {item.label}
            </Link>
          ),
        )}
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setPending(true);
            // Leave the protected shell before the auth state change can
            // trigger the dashboard guard's login redirect.
            router.push("/");
            void signOut().finally(() => {
              setPending(false);
              router.refresh();
            });
          }}
          className="rounded-lg px-2 py-2 text-xs font-medium text-slate-400 transition hover:text-white disabled:opacity-60 sm:text-sm"
        >
          {pending ? "Signing out…" : "Sign out"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <Link
        href="/login"
        className="rounded-lg px-2.5 py-2 text-xs font-medium text-slate-300 transition hover:text-white sm:text-sm"
      >
        Sign in
      </Link>
      <Link
        href="/signup"
        className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 sm:text-sm"
      >
        Create account
      </Link>
    </div>
  );
}
