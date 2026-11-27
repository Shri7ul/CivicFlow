"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  canAccessPath,
  homePathForRole,
  roleLabel,
} from "@/lib/auth/routing";
import type { ProfileRole } from "@/types/auth";

type FeatureLink = {
  path: string;
  label: string;
  group: string;
};

/** Role features shown in the ⋮ menu. Every entry is still RBAC-checked below. */
const ROLE_FEATURES: Record<ProfileRole, readonly FeatureLink[]> = {
  CITIZEN: [
    { path: "/dashboard", label: "Dashboard", group: "Overview" },
    { path: "/incidents", label: "My incidents", group: "Incidents" },
    { path: "/incidents/new", label: "Report incident", group: "Incidents" },
    { path: "/map", label: "Incident map", group: "Incidents" },
    { path: "/risk", label: "Risk map", group: "Insights" },
    { path: "/workforce/apply", label: "Apply as worker", group: "Workforce" },
    { path: "/workforce/status", label: "Application status", group: "Workforce" },
  ],
  WORKER: [
    { path: "/worker", label: "Assigned queue", group: "Field work" },
    { path: "/incidents", label: "Incident queue", group: "Field work" },
    { path: "/map", label: "Field map", group: "Field work" },
    { path: "/risk", label: "Risk map", group: "Insights" },
    { path: "/workforce/status", label: "Application status", group: "Account" },
  ],
  ADMIN: [
    { path: "/admin", label: "Admin overview", group: "Administration" },
    { path: "/admin?tab=applications", label: "Worker applications", group: "Administration" },
    { path: "/operations", label: "Incident triage & assignment", group: "Administration" },
    { path: "/incidents", label: "Incident queue", group: "Operations" },
    { path: "/risk", label: "Risk intelligence", group: "Operations" },
    { path: "/decisions", label: "Decisions", group: "Operations" },
    { path: "/validation", label: "Validation", group: "Operations" },
    { path: "/pilot", label: "Pilot readiness", group: "Operations" },
  ],
};

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

/**
 * Compact, accessible dropdown holding every role-specific surface. The bar
 * itself stays minimal; this is the only place role links are rendered.
 */
function FeatureMenu({ role }: { role: ProfileRole }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // Close after a route change so the menu never lingers over a new page.
  useEffect(() => {
    const timer = setTimeout(() => setOpen(false), 0);
    return () => clearTimeout(timer);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const pathOf = (item: FeatureLink) => item.path.split("?")[0] ?? item.path;
  const groups = new Map<string, FeatureLink[]>();
  for (const item of ROLE_FEATURES[role]) {
    // Defence in depth: never render a surface the role cannot reach.
    if (!canAccessPath(role, pathOf(item))) continue;
    const list = groups.get(item.group) ?? [];
    list.push(item);
    groups.set(item.group, list);
  }

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        aria-label="Open feature menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="feature-menu"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex size-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-lg leading-none text-slate-300 transition hover:border-white/20 hover:bg-white/10 hover:text-white"
      >
        <span aria-hidden="true">&#8942;</span>
      </button>
      <div
        id="feature-menu"
        role="menu"
        aria-label="Workspace features"
        hidden={!open}
        className="absolute right-0 top-full z-50 mt-2 w-[min(20rem,calc(100vw-2rem))] max-h-[min(32rem,70vh)] overflow-y-auto rounded-2xl border border-white/10 bg-slate-900/95 p-2 shadow-2xl shadow-black/40 backdrop-blur-xl"
      >
        {Array.from(groups.entries()).map(([group, items]) => (
          <div key={group} className="mb-1 last:mb-0">
            <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              {group}
            </p>
            {items.map((item) => {
              const active =
                pathname === pathOf(item) ||
                pathname.startsWith(`${pathOf(item)}/`);
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  role="menuitem"
                  aria-current={active ? "page" : undefined}
                  onClick={() => setOpen(false)}
                  className={`block rounded-lg px-3 py-2.5 text-sm transition ${
                    active
                      ? "bg-accent/10 font-medium text-emerald-200"
                      : "text-slate-200 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

type AuthAccountProps = {
  compact?: boolean;
  /** Show a slightly smaller badge on the public landing header. */
  minimal?: boolean;
};

/**
 * Account cluster. It is always rendered outside any scrollable link area and
 * pinned to the far right with `ml-auto`, so the badge and actions are never
 * clipped when the viewport is narrow.
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
        <Link
          href={homePathForRole(profile.role)}
          className="whitespace-nowrap rounded-lg px-2 py-2 text-xs font-medium text-slate-200 transition hover:text-white sm:px-3 sm:text-sm"
        >
          Dashboard
        </Link>
        <FeatureMenu role={profile.role} />
        {!compact ? (
          <span
            className={`text-right text-[11px] leading-4 text-muted ${
              minimal ? "xl:block" : "md:block"
            } hidden`}
          >
            <span className="block max-w-[10rem] truncate font-medium text-slate-200">
              {profile.full_name}
            </span>
            <span className="mt-0.5 inline-flex rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
              {roleLabel(profile.role)}
            </span>
          </span>
        ) : null}
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

type AuthNavProps = {
  compact?: boolean;
  /** Slightly smaller account cluster on the public product header. */
  minimal?: boolean;
};

export function AuthNav({ compact = false, minimal = false }: AuthNavProps) {
  return <AuthNavAccount compact={compact} minimal={minimal} />;
}
