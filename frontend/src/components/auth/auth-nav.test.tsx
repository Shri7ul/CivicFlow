import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const AUTH_STATE = vi.hoisted(() => ({
  status: "authenticated" as string,
  role: "ADMIN" as string,
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    status: AUTH_STATE.status,
    profile: {
      id: "user-1",
      full_name: "CivicFlow Test Admin",
      phone: null,
      role: AUTH_STATE.role,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    signOut: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/admin",
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import { AuthNavAccount } from "./auth-nav";

describe("AuthNav account cluster", () => {
  it("keeps a minimal right-pinned cluster with an accessible feature menu", () => {
    AUTH_STATE.role = "ADMIN";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("ml-auto");
    expect(html).toContain("shrink-0");
    expect(html).toContain("CivicFlow Test Admin");
    expect(html).toContain("Administrator");
    expect(html).toContain("Dashboard");
    expect(html).toContain('aria-label="Open feature menu"');
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('role="menu"');
    expect(html).toContain("Sign out");
    // The old inline role links must not clutter the bar again.
    expect(html).not.toContain("Apply as worker");
  });

  it("exposes admin features inside the menu", () => {
    AUTH_STATE.role = "ADMIN";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("Admin overview");
    expect(html).toContain("Worker applications");
    expect(html).toContain("Incident triage &amp; assignment");
    expect(html).toContain("Risk intelligence");
  });

  it("exposes citizen features inside the menu", () => {
    AUTH_STATE.role = "CITIZEN";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("My incidents");
    expect(html).toContain("Report incident");
    expect(html).toContain("Incident map");
    expect(html).toContain("Risk map");
    expect(html).toContain("Apply as worker");
  });

  it("exposes worker features inside the menu", () => {
    AUTH_STATE.role = "WORKER";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("Assigned queue");
    expect(html).toContain("Field map");
    expect(html).toContain("Application status");
    expect(html).not.toContain("Apply as worker");
  });

  it("pins the anonymous actions to the right too", () => {
    AUTH_STATE.status = "unauthenticated";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("ml-auto");
    expect(html).toContain("shrink-0");
    expect(html).toContain("Sign in");
    expect(html).toContain("Create account");
    AUTH_STATE.status = "authenticated";
    AUTH_STATE.role = "ADMIN";
  });
});
