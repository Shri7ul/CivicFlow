"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { safeNextPath } from "@/lib/auth/routing";

type AuthMode = "login" | "signup";

export function AuthForm({ mode }: { mode: AuthMode }) {
  const { status, error: authError, isConfigured, signIn, signUp } = useAuth();
  const router = useRouter();
  const [nextPath] = useState(() =>
    typeof window === "undefined"
      ? "/dashboard"
      : safeNextPath(new URLSearchParams(window.location.search).get("next")),
  );
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace(nextPath);
      router.refresh();
    }
  }, [nextPath, router, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setMessage(null);

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const fullName = String(form.get("full_name") ?? "").trim();

    if (!email.includes("@")) {
      setFormError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (mode === "signup" && password !== String(form.get("confirm_password") ?? "")) {
      setFormError("Passwords do not match.");
      return;
    }

    setPending(true);
    try {
      const result =
        mode === "login"
          ? await signIn(email, password)
          : await signUp(email, password, fullName);

      if (result.error) {
        setFormError(result.error);
        return;
      }
      if (result.needsEmailConfirmation) {
        setMessage(
          "Account created. Check your email to confirm your address, then sign in.",
        );
        return;
      }
      router.replace(nextPath);
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  const isLogin = mode === "login";
  const busy = pending || status === "loading";

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {!isConfigured ? (
        <p
          role="alert"
          className="rounded-xl border border-amber-300/20 bg-amber-300/5 px-4 py-3 text-sm text-amber-100"
        >
          Supabase environment variables are missing. Add
          <code className="mx-1 rounded bg-black/30 px-1 py-0.5 text-xs">
            NEXT_PUBLIC_SUPABASE_URL
          </code>
          and
          <code className="mx-1 rounded bg-black/30 px-1 py-0.5 text-xs">
            NEXT_PUBLIC_SUPABASE_ANON_KEY
          </code>
          to enable authentication.
        </p>
      ) : null}

      {mode === "signup" ? (
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
            Full name
          </span>
          <input
            name="full_name"
            type="text"
            autoComplete="name"
            maxLength={200}
            placeholder="Your name"
            className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/20"
          />
        </label>
      ) : null}

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
          Email
        </span>
        <input
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
          className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/20"
        />
      </label>

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
          Password
        </span>
        <input
          name="password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          required
          minLength={8}
          placeholder="At least 8 characters"
          className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/20"
        />
      </label>

      {isLogin ? (
        <div className="-mt-2 text-right">
          <Link
            href="/forgot-password"
            className="text-xs font-medium text-emerald-300 underline-offset-4 hover:underline"
          >
            Forgot password?
          </Link>
        </div>
      ) : null}

      {mode === "signup" ? (
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
            Confirm password
          </span>
          <input
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            placeholder="Repeat your password"
            className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/20"
          />
        </label>
      ) : null}

      {formError || authError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-300/20 bg-rose-300/5 px-4 py-3 text-sm text-rose-100"
        >
          {formError ?? authError}
        </p>
      ) : null}

      {message ? (
        <p
          role="status"
          className="rounded-xl border border-emerald-300/20 bg-emerald-300/5 px-4 py-3 text-sm text-emerald-100"
        >
          {message}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy || !isConfigured}
        className="w-full rounded-xl bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending
          ? isLogin
            ? "Signing in…"
            : "Creating account…"
          : isLogin
            ? "Sign in"
            : "Create account"}
      </button>

      <p className="pt-1 text-center text-sm text-slate-400">
        {isLogin ? "New to CivicFlow?" : "Already have an account?"}{" "}
        <Link
          href={isLogin ? "/signup" : "/login"}
          className="font-medium text-emerald-300 underline-offset-4 hover:underline"
        >
          {isLogin ? "Create an account" : "Sign in"}
        </Link>
      </p>
    </form>
  );
}
