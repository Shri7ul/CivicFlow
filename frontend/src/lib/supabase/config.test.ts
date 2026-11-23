import { describe, expect, it } from "vitest";

import { isSupabaseConfigured } from "@/lib/supabase/config";

const anonKey = "sb_publishable_abcdefghijklmnopqrstuvwxyz123456";

describe("Supabase public configuration", () => {
  it("accepts an https project URL and public anon key", () => {
    expect(
      isSupabaseConfigured({
        url: "https://project.supabase.co",
        anonKey,
      }),
    ).toBe(true);
  });

  it("rejects missing configuration", () => {
    expect(isSupabaseConfigured({ url: "", anonKey: "" })).toBe(false);
    expect(
      isSupabaseConfigured({ url: "not-a-url", anonKey }),
    ).toBe(false);
    expect(
      isSupabaseConfigured({ url: "https://project.supabase.co", anonKey: "short" }),
    ).toBe(false);
  });

  it("never accepts a service-role key in browser configuration", () => {
    expect(
      isSupabaseConfigured({
        url: "https://project.supabase.co",
        anonKey: `${anonKey}-service_role`,
      }),
    ).toBe(false);
  });
});
