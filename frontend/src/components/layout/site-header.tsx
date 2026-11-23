import Link from "next/link";

import { AuthNav } from "@/components/auth/auth-nav";
import { getApiBaseUrl } from "@/lib/api/client";
import { siteConfig } from "@/config/app";

function LogoMark() {
  return (
    <span className="flex size-9 items-center justify-center rounded-xl border border-emerald-400/25 bg-emerald-400/10">
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        className="size-5 text-emerald-300"
      >
        <path
          d="M5 17.5V13m7 4.5V8m7 9.5V5.5"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <path
          d="M3.5 20.5h17"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          opacity=".45"
        />
      </svg>
    </span>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-slate-950/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link
          href="/"
          className="flex items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
        >
          <LogoMark />
          <span>
            <span className="block text-sm font-semibold tracking-tight text-white">
              {siteConfig.name}
            </span>
            <span className="hidden text-[10px] uppercase tracking-[0.2em] text-slate-500 sm:block">
              Urban response intelligence
            </span>
          </span>
        </Link>

        <nav
          aria-label="Primary navigation"
          className="flex items-center gap-1 sm:gap-2"
        >
          <Link
            href="/#status"
            className="rounded-lg px-2.5 py-2 text-xs font-medium text-slate-400 transition hover:text-white sm:px-3 sm:text-sm"
          >
            Status
          </Link>
          <Link
            href="/#architecture"
            className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-400 transition hover:text-white sm:block"
          >
            Architecture
          </Link>
          <a
            href={`${getApiBaseUrl()}/docs`}
            target="_blank"
            rel="noreferrer"
            className="hidden items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/10 md:inline-flex sm:text-sm"
          >
            API docs
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              fill="none"
              className="size-3.5 text-slate-500"
            >
              <path
                d="M6 3.5h6.5V10M12 4 4 12"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
          <span aria-hidden="true" className="mx-1 h-5 w-px bg-white/10" />
          <AuthNav />
        </nav>
      </div>
    </header>
  );
}
