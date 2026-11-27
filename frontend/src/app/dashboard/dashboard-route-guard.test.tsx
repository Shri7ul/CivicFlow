import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const STATE = vi.hoisted(() => ({
  status: "authenticated" as string,
  role: "CITIZEN" as string,
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    status: STATE.status,
    profile:
      STATE.status === "authenticated"
        ? {
            id: "user-1",
            full_name: "Test User",
            phone: null,
            role: STATE.role,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          }
        : null,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

import { DashboardRouteGuard } from "./dashboard-route-guard";

const child = <p data-testid="workspace">Workspace overview</p>;

function render() {
  return renderToStaticMarkup(<DashboardRouteGuard>{child}</DashboardRouteGuard>);
}

describe("DashboardRouteGuard", () => {
  it("never paints the Citizen workspace for an ADMIN", () => {
    STATE.status = "authenticated";
    STATE.role = "ADMIN";
    expect(render()).not.toContain("Workspace overview");
  });

  it("never paints the Citizen workspace for a WORKER", () => {
    STATE.role = "WORKER";
    expect(render()).not.toContain("Workspace overview");
  });

  it("renders the workspace for a resolved CITIZEN", () => {
    STATE.role = "CITIZEN";
    expect(render()).toContain("Workspace overview");
  });

  it("renders nothing while the profile is still loading", () => {
    STATE.status = "loading";
    expect(render()).not.toContain("Workspace overview");
    STATE.status = "authenticated";
  });
});
