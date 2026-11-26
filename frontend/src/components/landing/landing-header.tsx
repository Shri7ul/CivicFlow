"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthNav } from "@/components/auth/auth-nav";
import {
  landingNavLinks,
  landingSections,
} from "@/components/landing/landing-content";

function BrandMark() {
  return (
    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-accent/25 bg-accent/10">
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        className="size-5 text-accent"
      >
        <path
          d="M5 17.5V12m7 5.5V7m7 10.5V4.5"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <path
          d="M3.5 20.5h17"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          opacity="0.45"
        />
      </svg>
    </span>
  );
}

export function LandingHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const nodes = landingSections
      .map(({ id }) => document.getElementById(id))
      .filter((node): node is HTMLElement => node !== null);
    if (nodes.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-40% 0px -45% 0px", threshold: [0, 0.25, 0.5] },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-5 sm:px-8 lg:px-10">
        <Link
          href="/"
          className="flex min-w-0 items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
        >
          <BrandMark />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold tracking-tight text-foreground">
              CivicFlow
            </span>
            <span className="hidden truncate text-[10px] uppercase tracking-[0.18em] text-muted sm:block">
              Urban Response Intelligence
            </span>
          </span>
        </Link>

        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-1 lg:flex"
        >
          {landingNavLinks.map(({ label, href }) => {
            const id = href.slice(1);
            const active = activeId === id;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "location" : undefined}
                className={`relative rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "text-foreground"
                    : "text-muted transition hover:text-foreground"
                }`}
              >
                {label}
                {active ? (
                  <span
                    aria-hidden="true"
                    className="absolute inset-x-3 -bottom-px h-px bg-accent"
                  />
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="hidden lg:block">
          <AuthNav minimal />
        </div>

        <button
          type="button"
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={menuOpen}
          aria-controls="landing-mobile-nav"
          onClick={() => setMenuOpen((value) => !value)}
          className="inline-flex size-10 items-center justify-center rounded-lg border border-line bg-surface text-foreground transition hover:border-line/80 hover:bg-surface-raised lg:hidden"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            className="size-5"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
          >
            {menuOpen ? (
              <path d="M6 6l12 12M18 6 6 18" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" />
            )}
          </svg>
        </button>
      </div>

      {menuOpen ? (
        <nav
          id="landing-mobile-nav"
          aria-label="Mobile navigation"
          className="border-t border-line bg-background px-5 pb-5 pt-2 sm:px-8 lg:hidden"
        >
          <ul className="flex flex-col">
            {landingNavLinks.map(({ label, href }) => (
              <li key={href}>
                <Link
                  href={href}
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-lg px-2 py-3 text-sm text-foreground transition hover:bg-surface"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-2 border-t border-line pt-4">
            <AuthNav minimal />
          </div>
        </nav>
      ) : null}
    </header>
  );
}
