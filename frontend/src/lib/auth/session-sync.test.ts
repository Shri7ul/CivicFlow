import { describe, expect, it } from "vitest";

import type { Profile } from "@/types/auth";
import { profileUnchanged, shouldSilentlySync } from "@/lib/auth/session-sync";

const PROFILE: Profile = {
  id: "user-1",
  full_name: "Test User",
  phone: null,
  role: "CITIZEN",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("profileUnchanged", () => {
  it("treats an identical profile as unchanged", () => {
    expect(profileUnchanged(PROFILE, { ...PROFILE })).toBe(true);
  });

  it("ignores volatile field drift on a tab-focus refresh", () => {
    expect(
      profileUnchanged(PROFILE, {
        ...PROFILE,
        updated_at: "2026-11-27T12:00:00Z",
        full_name: "Test User ",
        phone: "+8801700000000",
      }),
    ).toBe(true);
  });

  it("detects a database role promotion", () => {
    expect(
      profileUnchanged(PROFILE, { ...PROFILE, role: "ADMIN", updated_at: "later" }),
    ).toBe(false);
  });

  it("detects deactivation", () => {
    expect(profileUnchanged(PROFILE, { ...PROFILE, is_active: false })).toBe(false);
  });

  it("detects a different user", () => {
    expect(profileUnchanged(PROFILE, { ...PROFILE, id: "user-2" })).toBe(false);
  });

  it("is false when nothing is cached yet", () => {
    expect(profileUnchanged(null, PROFILE)).toBe(false);
  });
});

describe("shouldSilentlySync", () => {
  it("keeps cached UI for a token refresh on tab focus", () => {
    expect(shouldSilentlySync("TOKEN_REFRESHED", "user-1", "user-1", true)).toBe(true);
    expect(shouldSilentlySync("SIGNED_IN", "user-1", "user-1", true)).toBe(true);
  });

  it("stays silent for any event while the same user is cached", () => {
    expect(shouldSilentlySync("USER_UPDATED", "user-1", "user-1", true)).toBe(true);
    expect(shouldSilentlySync("PASSWORD_RECOVERY", "user-1", "user-1", true)).toBe(true);
  });

  it("does not go silent for a new identity or first load", () => {
    expect(shouldSilentlySync("SIGNED_IN", null, "user-1", false)).toBe(false);
    expect(shouldSilentlySync("SIGNED_IN", "user-1", "user-2", true)).toBe(false);
  });

  it("still performs a full sync on sign out or deletion", () => {
    expect(shouldSilentlySync("SIGNED_OUT", "user-1", "user-1", true)).toBe(false);
    expect(shouldSilentlySync("USER_DELETED", "user-1", "user-1", true)).toBe(false);
  });
});
