import type { ReactNode } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <main className="flex flex-1 items-center justify-center px-5 py-14 sm:px-8">
        <div className="grid w-full max-w-5xl gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <section className="hidden lg:block">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
              {eyebrow}
            </p>
            <h1 className="mt-4 max-w-lg text-4xl font-semibold tracking-tight text-white">
              {title}
            </h1>
            <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
              {subtitle}
            </p>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-3">
              {[
                ["Citizen", "Report and track"],
                ["Worker", "Coordinate response"],
                ["Admin", "Govern access"],
              ].map(([role, detail]) => (
                <div
                  key={role}
                  className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
                >
                  <dt className="text-xs font-semibold text-white">{role}</dt>
                  <dd className="mt-1 text-[11px] leading-4 text-slate-500">
                    {detail}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="mx-auto w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/60 p-6 shadow-2xl shadow-black/30 sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300 lg:hidden">
              {eyebrow}
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white lg:mt-0">
              {title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">{subtitle}</p>
            <div className="mt-6">{children}</div>
            <p className="mt-6 text-center text-[11px] leading-5 text-slate-500">
              Roles are assigned by CivicFlow administrators. Sign-up always
              creates a Citizen account.
            </p>
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
