import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const AUTH_STATE = vi.hoisted(() => ({ status: "authenticated" as string }));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    status: AUTH_STATE.status,
    profile: {
      id: "user-1",
      full_name: "CivicFlow Test Admin",
      phone: null,
      role: "ADMIN",
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
  it("pins the authenticated profile badge and actions to the right", () => {
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("ml-auto");
    expect(html).toContain("shrink-0");
    expect(html).toContain("CivicFlow Test Admin");
    expect(html).toContain("Administrator");
    expect(html).toContain("Admin workspace");
    expect(html).toContain("Sign out");
  });

  it("pins the anonymous actions to the right too", () => {
    AUTH_STATE.status = "unauthenticated";
    const html = renderToStaticMarkup(<AuthNavAccount />);
    expect(html).toContain("ml-auto");
    expect(html).toContain("shrink-0");
    expect(html).toContain("Sign in");
    expect(html).toContain("Create account");
    AUTH_STATE.status = "authenticated";
  });
});
