import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

describe("frontend production security headers", () => {
  it("applies baseline headers to every route", async () => {
    const groups = await nextConfig.headers?.() as Array<{
      source: string;
      headers: Array<{ key: string; value: string }>;
    }>;

    expect(groups).not.toBeUndefined();
    expect(groups?.[0]?.source).toBe("/:path*");

    const values = new Map(
      (groups?.[0]?.headers ?? []).map((item) => [item.key.toLowerCase(), item.value]),
    );

    expect(values.get("x-content-type-options")).toBe("nosniff");
    expect(values.get("x-frame-options")).toBe("DENY");
    expect(values.get("referrer-policy")).toBe("no-referrer");
    expect(values.get("permissions-policy")).toContain("geolocation=()");

    const csp = values.get("content-security-policy") ?? "";
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("does not embed any service-role credential in the client configuration", () => {
    const serialized = JSON.stringify(nextConfig).toLowerCase();
    expect(serialized).not.toContain("service_role");
    expect(serialized).not.toContain("supabase_service_role_key");
  });
});
