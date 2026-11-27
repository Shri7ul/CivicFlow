"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { homePathForRole, navigationForRole, roleLabel } from "@/lib/auth/routing";

const NAV_ITEMS = [
  { path: "/dashboard", label: "Dashboard" },
  { path: "/incidents", label: "My incidents" },
  { path: "/map", label: "Map" },
  { path: "/risk", label: "Risk intelligence" },
  { path: "/operations", label: "Incident review" },
  { path: "/decisions", label: "Decisions" },
  { path: "/validation", label: "Validation" },
  { path: "/pilot", label: "Pilot" },
  { path: "/workforce/apply", label: "Apply" },
  { path: "/workforce/status", label: "Application" },
  { path: "/worker", label: "Worker desk" },
  { path: "/admin", label: "Admin operations" },
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

type AuthAccountProps = {
  compact?: boolean;
  /** Show only the workspace entry on a public product header. */
  minimal?: boolean;
};

/**
 * Account cluster. It is always rendered outside the scrollable link area and
 * pinned to the far right with `ml-auto`, so the profile badge and actions are
 * never clipped when the viewport is narrow.
 */
export function AuthNavAccount({ compact = false, minimal = false }: AuthAccountProps) {
  const { status, profile } = useAuth();

  if (status === "loading") {
    return (
      <div className="ml-auto flex shrink-0 items-center pl-2">
        <span
          aria-label="Loading account"
          className="inline-block h-8 w-20 animate-pulse rounded-lg bg-white/5"
        />
      </div>
    );
  }

  if (status === "authenticated" && profile) {
    return (
      <div className="ml-auto flex shrink-0 items-center gap-2 pl-2">
        {!compact ? (
          <span
            className={`hidden text-right text-[11px] leading-4 text-muted ${
              minimal ? "xl:block" : "lg:block"
            }`}
          >
            <span className="block font-medium text-slate-200">
              {profile.full_name}
            </span>
            {roleLabel(profile.role)}
          </span>
        ) : null}
        <Link
          href={homePathForRole(profile.role)}
          className="whitespace-nowrap rounded-lg border border-accent/25 bg-accent/10 px-3 py-2 text-xs font-medium text-accent transition hover:bg-accent/15 sm:text-sm"
        >
          {profile.role === "ADMIN"
            ? "Admin workspace"
            : profile.role === "WORKER"
              ? "Worker workspace"
              : "My workspace"}
        </Link>
        <SignOutControl />
      </div>
    );
  }

  return (
    <div className="ml-auto flex shrink-0 items-center gap-1.5 pl-2">
      <Link
        href="/login"
        className="whitespace-nowrap rounded-lg px-2.5 py-2 text-xs font-medium text-slate-300 transition hover:text-white sm:text-sm"
      >
        Sign in
      </Link>
      <Link
        href="/signup"
        className="whitespace-nowrap rounded-lg border border-white/10 bg-white/5 px-2.5 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 sm:text-sm"
      >
        Create account
      </Link>
    </div>
  );
}

/** Role-specific links only; the shell owns the scroll container. */
export function AuthNavLinks() {
  const { status, profile } = useAuth();
  const pathname = usePathname();

  if (status !== "authenticated" || !profile) {
    return null;
  }

  return (
    <>
      {NAV_ITEMS.filter((item) =>
        navigationForRole(profile.role).includes(item.path),
      ).map((item) => {
        const active =
          pathname === item.path || pathname.startsWith(`${item.path}/`);
        const highlighted = active || item.path === homePathForRole(profile.role);
        return (
          <Link
            key={item.path}
            href={item.path}
            aria-current={active ? "page" : undefined}
            className={
              highlighted
                ? "whitespace-nowrap rounded-lg border border-accent/25 bg-accent/10 px-2.5 py-2 text-xs font-medium text-emerald-200 transition hover:bg-accent/15 sm:px-3 sm:text-sm"
                : "whitespace-nowrap rounded-lg px-2.5 py-2 text-xs font-medium text-slate-300 transition hover:text-white sm:text-sm"
            }
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

type AuthNavProps = {
  compact?: boolean;
  /** Show only the workspace entry and sign-out on a public product header. */
  minimal?: boolean;
};

export function AuthNav({ compact = false, minimal = false }: AuthNavProps) {
  if (minimal) {
    return <AuthNavAccount compact={compact} minimal />;
  }

  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <nav
        aria-label="Workspace navigation"
        className="flex min-w-0 items-center gap-1 overflow-x-auto whitespace-nowrap [scrollbar-width:none] sm:gap-2"
      >
        <AuthNavLinks />
      </nav>
      <AuthNavAccount compact={compact} />
    </div>
  );
}
