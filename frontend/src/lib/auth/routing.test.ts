import { describe, expect, it } from "vitest";

import {
  buildLoginHref,
  canAccessPath,
  hasSupabaseAuthCookie,
  isProtectedPath,
  navigationForRole,
  roleLabel,
  safeNextPath,
} from "@/lib/auth/routing";
import { deriveAuthStatus, isAuthReady } from "@/lib/auth/state";

describe("protected routing", () => {
  it("recognizes dashboard and incident paths", () => {
    expect(isProtectedPath("/dashboard")).toBe(true);
    expect(isProtectedPath("/dashboard/reports")).toBe(true);
    expect(isProtectedPath("/incidents")).toBe(true);
    expect(isProtectedPath("/incidents/new")).toBe(true);
    expect(isProtectedPath("/incidents/abc")).toBe(true);
    expect(isProtectedPath("/map")).toBe(true);
    expect(isProtectedPath("/risk")).toBe(true);
    expect(isProtectedPath("/risk/cells/abc")).toBe(true);
    expect(isProtectedPath("/operations")).toBe(true);
    expect(isProtectedPath("/operations/alerts")).toBe(true);
    expect(isProtectedPath("/decisions")).toBe(true);
    expect(isProtectedPath("/decisions/abc")).toBe(true);
    expect(isProtectedPath("/risky")).toBe(false);
    expect(isProtectedPath("/decisionish")).toBe(false);
    expect(isProtectedPath("/maplike")).toBe(false);
    expect(isProtectedPath("/dashboardish")).toBe(false);
    expect(isProtectedPath("/validation")).toBe(true);
    expect(isProtectedPath("/validation/evidence")).toBe(true);
    expect(isProtectedPath("/pilot")).toBe(true);
    expect(isProtectedPath("/pilot/geography")).toBe(true);
    expect(isProtectedPath("/login")).toBe(false);
  });

  it("prevents open redirects and auth-page loops", () => {
    expect(safeNextPath("/dashboard/reports?tab=open")).toBe(
      "/dashboard/reports?tab=open",
    );
    expect(safeNextPath("https://evil.example")).toBe("/dashboard");
    expect(safeNextPath("//evil.example")).toBe("/dashboard");
    expect(safeNextPath("/\\evil.example")).toBe("/dashboard");
    expect(safeNextPath("/login?next=/dashboard")).toBe("/dashboard");
    expect(safeNextPath("/auth/callback")).toBe("/dashboard");
    expect(safeNextPath(null)).toBe("/dashboard");
  });

  it("builds a login URL with only a safe next value", () => {
    expect(buildLoginHref("/dashboard/reports")).toBe(
      "/login?next=%2Fdashboard%2Freports",
    );
    expect(buildLoginHref("/dashboard")).toBe("/login");
    expect(buildLoginHref("https://evil.example")).toBe("/login");
  });
});

describe("role-aware navigation", () => {
  it("shows only modules a citizen can actually use", () => {
    const paths = navigationForRole("CITIZEN");
    expect(paths).toContain("/dashboard");
    expect(paths).toContain("/incidents");
    expect(paths).toContain("/map");
    expect(paths).toContain("/risk");
    expect(paths).not.toContain("/decisions");
    expect(paths).not.toContain("/operations");
    expect(paths).not.toContain("/validation");
    expect(canAccessPath("CITIZEN", "/operations")).toBe(false);
    expect(canAccessPath("CITIZEN", "/validation/report")).toBe(false);
    expect(canAccessPath("CITIZEN", "/incidents/123")).toBe(true);
  });

  it("shows staff modules to workers and admins", () => {
    for (const role of ["WORKER", "ADMIN"] as const) {
      const paths = navigationForRole(role);
      expect(paths).toContain("/decisions");
      expect(paths).toContain("/operations");
      expect(paths).toContain("/validation");
      expect(paths).toContain("/pilot");
      expect(canAccessPath(role, "/operations/alerts")).toBe(true);
    }
  });
});

describe("optimistic Supabase cookie check", () => {
  it("accepts base and chunked Supabase auth cookies", () => {
    expect(
      hasSupabaseAuthCookie([{ name: "sb-project-ref-auth-token" }]),
    ).toBe(true);
    expect(
      hasSupabaseAuthCookie([{ name: "sb-project-ref-auth-token.0" }]),
    ).toBe(true);
  });

  it("ignores unrelated cookies", () => {
    expect(hasSupabaseAuthCookie([{ name: "sb-project-ref-code-verifier" }])).toBe(
      false,
    );
    expect(hasSupabaseAuthCookie([{ name: "theme" }])).toBe(false);
  });
});

describe("auth state", () => {
  it("maps configuration, session, and profile into one status", () => {
    expect(
      deriveAuthStatus({
        configured: false,
        sessionPresent: false,
        profilePresent: false,
      }),
    ).toBe("unconfigured");
    expect(
      deriveAuthStatus({
        configured: true,
        sessionPresent: false,
        profilePresent: false,
      }),
    ).toBe("unauthenticated");
    expect(
      deriveAuthStatus({
        configured: true,
        sessionPresent: true,
        profilePresent: false,
      }),
    ).toBe("loading");
    expect(
      deriveAuthStatus({
        configured: true,
        sessionPresent: true,
        profilePresent: true,
      }),
    ).toBe("authenticated");
    expect(
      deriveAuthStatus({
        configured: true,
        sessionPresent: true,
        profilePresent: false,
        error: "backend unavailable",
      }),
    ).toBe("error");
  });

  it("reports ready states", () => {
    expect(isAuthReady("authenticated")).toBe(true);
    expect(isAuthReady("unauthenticated")).toBe(true);
    expect(isAuthReady("unconfigured")).toBe(true);
    expect(isAuthReady("loading")).toBe(false);
    expect(isAuthReady("error")).toBe(false);
  });

  it("uses human-readable role labels", () => {
    expect(roleLabel("CITIZEN")).toBe("Citizen");
    expect(roleLabel("WORKER")).toBe("Field worker");
    expect(roleLabel("ADMIN")).toBe("Administrator");
  });
});
