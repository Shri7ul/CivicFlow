"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { getEmailRedirectTo } from "@/lib/auth/redirect";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

const inputClass =
  "w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-400/20";

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setMessage(null);
    const email = String(
      new FormData(event.currentTarget).get("email") ?? "",
    ).trim();
    if (!email.includes("@")) {
      setFormError("Enter a valid email address.");
      return;
    }
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setFormError("Supabase authentication is not configured.");
      return;
    }
    setPending(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        // The callback exchanges the PKCE code, then hands the user to the
        // new-password form. The redirect origin is config-driven, never
        // inferred from a browser in production.
        redirectTo: getEmailRedirectTo(
          "/auth/callback?next=%2Fupdate-password",
        ),
      });
      if (error) {
        setFormError(error.message);
        return;
      }
      // Deliberately identical for known and unknown addresses.
      setMessage(
        "If an account exists for that address, a password reset link is on its way. Check your inbox.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
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
          className={inputClass}
        />
      </label>

      {formError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-300/20 bg-rose-300/5 px-4 py-3 text-sm text-rose-100"
        >
          {formError}
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
        disabled={pending}
        className="w-full rounded-xl bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Sending link…" : "Send reset link"}
      </button>
      <p className="pt-1 text-center text-sm text-slate-400">
        Remembered it?{" "}
        <Link
          href="/login"
          className="font-medium text-emerald-300 underline-offset-4 hover:underline"
        >
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
