"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { readCallbackParameters } from "@/lib/auth/callback";

type CallbackState = "working" | "error";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [state, setState] = useState<CallbackState>("working");
  const [message, setMessage] = useState("Completing sign in…");

  useEffect(() => {
    void (async () => {
      // Defer state updates out of the synchronous effect body.
      await Promise.resolve();
      const { code, errorDescription, next } = readCallbackParameters(
        window.location.search,
      );
      const supabase = getSupabaseBrowserClient();

      if (errorDescription) {
        setState("error");
        setMessage(errorDescription);
        return;
      }
      if (!supabase) {
        setState("error");
        setMessage("Supabase authentication is not configured.");
        return;
      }
      if (!code) {
        setState("error");
        setMessage("The sign-in link is missing its authorization code.");
        return;
      }

      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (error) {
        setState("error");
        setMessage(error.message);
        return;
      }
      router.replace(next);
      router.refresh();
    })();
  }, [router]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-slate-950 px-5">
      <div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-center">
        <h1 className="text-xl font-semibold text-white">
          {state === "working" ? "Finishing sign in" : "Sign-in problem"}
        </h1>
        <p
          role={state === "error" ? "alert" : "status"}
          className="mt-3 text-sm leading-6 text-slate-400"
        >
          {message}
        </p>
        {state === "error" ? (
          <Link
            href="/login"
            className="mt-6 inline-flex rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950"
          >
            Back to sign in
          </Link>
        ) : null}
      </div>
    </main>
  );
}
