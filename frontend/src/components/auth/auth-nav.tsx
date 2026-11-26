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
  { path: "/workforce/apply", label: "Apply" },
  { path: "/workforce/status", label: "Application" },
  { path: "/worker", label: "Worker desk" },
  { path: "/admin", label: "Admin" },
  { path: "/dashboard", label: "Dashboard" },
] as const;

/** Shared by the full app shell and the compact public landing header. */
function SignOutControl() {
  const { signOut } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);

  return (
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
      className="rounded-lg px-2 py-2 text-xs font-medium text-muted transition hover:text-foreground disabled:opacity-60 sm:text-sm"
    >
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}

type AuthNavProps = {
  compact?: boolean;
  /** Show only the workspace entry and sign-out on a public product header. */
  minimal?: boolean;
};

export function AuthNav({ compact = false, minimal = false }: AuthNavProps) {
  const { status, profile } = useAuth();

  if (status === "loading") {
    return (
      <span
        aria-label="Loading account"
        className="inline-block h-8 w-20 animate-pulse rounded-lg bg-white/5"
      />
    );
  }

  if (status === "authenticated" && profile) {
    if (minimal) {
      return (
        <div className="flex items-center gap-2">
          <span className="hidden text-right text-[11px] leading-4 text-muted xl:block">
            {roleLabel(profile.role)}
          </span>
          <Link
            href="/dashboard"
            className="rounded-lg border border-accent/25 bg-accent/10 px-3 py-2 text-xs font-medium text-accent transition hover:bg-accent/15 sm:text-sm"
          >
            Workspace
          </Link>
          <SignOutControl />
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2">
        {!compact ? (
          <span className="hidden text-right text-[11px] leading-4 text-muted lg:block">
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
              className="rounded-lg border border-accent/25 bg-accent/10 px-2.5 py-2 text-xs font-medium text-emerald-200 transition hover:bg-accent/15 sm:px-3 sm:text-sm"
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
        <SignOutControl />
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
