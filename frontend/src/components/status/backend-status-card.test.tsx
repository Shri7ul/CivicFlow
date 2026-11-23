import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BackendStatusCard } from "./backend-status-card";

const endpoint = "http://localhost:8000/api/v1/health";
const noop = () => undefined;

describe("BackendStatusCard", () => {
  it("renders a loading state while the real request is in flight", () => {
    const html = renderToStaticMarkup(
      <BackendStatusCard
        state={{ status: "loading", data: null, error: null, checkedAt: null }}
        endpoint={endpoint}
        onRefresh={noop}
      />,
    );

    expect(html).toContain("Checking the live API");
    expect(html).toContain(endpoint);
  });

  it("renders service details only after a healthy response", () => {
    const html = renderToStaticMarkup(
      <BackendStatusCard
        state={{
          status: "healthy",
          data: {
            status: "healthy",
            service: "CivicFlow API",
            environment: "development",
            version: "v1",
          },
          error: null,
          checkedAt: "2026-01-01T12:00:00.000Z",
        }}
        endpoint={endpoint}
        onRefresh={noop}
      />,
    );

    expect(html).toContain("The API is responding.");
    expect(html).toContain("CivicFlow API");
    expect(html).toContain("development");
    expect(html).toContain("12:00:00 UTC");
  });

  it("renders a safe error state when the backend is unavailable", () => {
    const html = renderToStaticMarkup(
      <BackendStatusCard
        state={{
          status: "error",
          data: null,
          error: "Unable to reach the CivicFlow API.",
          checkedAt: null,
        }}
        endpoint={endpoint}
        onRefresh={noop}
      />,
    );

    expect(html).toContain("The API is not reachable.");
    expect(html).toContain("Unable to reach the CivicFlow API.");
  });
});
