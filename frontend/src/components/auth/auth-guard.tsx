"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { buildLoginHref } from "@/lib/auth/routing";
import { isAuthReady } from "@/lib/auth/state";

function GuardFrame({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center justify-center px-5 py-16">
      {children}
    </div>
  );
}

function LoadingCard({ label }: { label: string }) {
  return (
    <div className="w-full rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-center">
      <p className="text-sm text-slate-300" role="status">
        {label}
      </p>
    </div>
  );
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status, error, isConfigured, refreshProfile, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(buildLoginHref(pathname));
    }
  }, [pathname, router, status]);

  if (!isConfigured || status === "unconfigured") {
    return (
      <GuardFrame>
        <div className="w-full rounded-3xl border border-amber-300/20 bg-amber-300/5 p-8">
          <h1 className="text-lg font-semibold text-white">
            Authentication is not configured
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Add the public Supabase project URL and anon key to
            <code className="mx-1 rounded bg-black/30 px-1.5 py-0.5 text-xs">
              frontend/.env.local
            </code>
            to enable sign-in.
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white"
          >
            Return home
          </Link>
        </div>
      </GuardFrame>
    );
  }

  if (status === "loading") {
    return (
      <GuardFrame>
        <LoadingCard label="Checking your CivicFlow session…" />
      </GuardFrame>
    );
  }

  if (status === "error") {
    return (
      <GuardFrame>
        <div className="w-full rounded-3xl border border-rose-300/20 bg-rose-300/5 p-8">
          <h1 className="text-lg font-semibold text-white">
            We could not load your profile
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-300">{error}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void refreshProfile()}
              className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white"
            >
              Sign out
            </button>
          </div>
        </div>
      </GuardFrame>
    );
  }

  if (!isAuthReady(status) || status === "unauthenticated") {
    return (
      <GuardFrame>
        <LoadingCard label="Redirecting to sign in…" />
      </GuardFrame>
    );
  }

  return <>{children}</>;
}
