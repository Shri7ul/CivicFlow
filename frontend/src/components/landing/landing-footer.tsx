import Link from "next/link";

import {
  copyrightYear,
  landingFooterLinks,
} from "@/components/landing/landing-content";

export function LandingFooter() {
  return (
    <footer className="border-t border-line bg-surface/40">
      <div className="mx-auto grid w-full max-w-7xl gap-10 px-5 py-12 sm:px-8 lg:grid-cols-[minmax(0,1.4fr)_repeat(2,minmax(0,1fr))] lg:px-10">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg border border-accent/25 bg-accent/10">
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                className="size-4 text-accent"
              >
                <path
                  d="M5 17.5V12m7 5.5V7m7 10.5V4.5M3.5 20.5h17"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <span className="text-sm font-semibold tracking-tight text-foreground">
              CivicFlow
            </span>
          </div>
          <p className="mt-4 max-w-xs text-sm leading-6 text-muted">
            Urban response intelligence — a unified workspace for incidents,
            spatial context and governed decision support.
          </p>
        </div>

        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
            Product
          </h2>
          <ul className="mt-4 flex flex-col gap-3">
            {landingFooterLinks.slice(0, 4).map(({ label, href }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="text-sm text-muted transition hover:text-foreground"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
            Access
          </h2>
          <ul className="mt-4 flex flex-col gap-3">
            {landingFooterLinks.slice(4).map(({ label, href }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="text-sm text-muted transition hover:text-foreground"
                >
                  {label}
                </Link>
              </li>
            ))}
            <li>
              <Link
                href="/signup"
                className="text-sm text-muted transition hover:text-foreground"
              >
                Create account
              </Link>
            </li>
          </ul>
          <p className="mt-6 max-w-[15rem] text-xs leading-5 text-muted/60">
            Interface previews on this page are illustrative and do not
            represent live data.
          </p>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-5 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
          <p>
            © {copyrightYear} CivicFlow. Urban response intelligence.
          </p>
          <p>Role-aware access · Explainable analysis · Governed workflows</p>
        </div>
      </div>
    </footer>
  );
}
