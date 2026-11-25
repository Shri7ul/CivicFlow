import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTH_CALLBACK_PATH,
  DEFAULT_SITE_ORIGIN,
  getConfiguredSiteOrigin,
  getEmailRedirectTo,
  getSiteOrigin,
  isLocalRedirect,
} from "./redirect";

const PRODUCTION_ORIGIN = "https://civic-flow-lilac.vercel.app";

function setBrowserOrigin(origin: string | null): void {
  if (origin === null) {
    vi.stubGlobal("window", undefined);
  } else {
    vi.stubGlobal("window", { location: { origin } });
  }
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("email verification redirect selection", () => {
  it("uses the configured site origin for registration redirects", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", PRODUCTION_ORIGIN);
    setBrowserOrigin("http://localhost:3000");
    expect(getConfiguredSiteOrigin()).toBe(PRODUCTION_ORIGIN);
    expect(getEmailRedirectTo()).toBe(`${PRODUCTION_ORIGIN}${AUTH_CALLBACK_PATH}`);
  });

  it("builds the production verification callback URL", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", `${PRODUCTION_ORIGIN}/`);
    expect(getEmailRedirectTo()).toBe(`${PRODUCTION_ORIGIN}/auth/callback`);
  });

  it("builds a password-recovery callback that targets the update-password page", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", PRODUCTION_ORIGIN);
    expect(
      getEmailRedirectTo("/auth/callback?next=%2Fupdate-password"),
    ).toBe(
      `${PRODUCTION_ORIGIN}/auth/callback?next=%2Fupdate-password`,
    );
  });

  it("builds the development verification callback URL", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "");
    setBrowserOrigin(DEFAULT_SITE_ORIGIN);
    expect(getEmailRedirectTo()).toBe("http://localhost:3000/auth/callback");
    expect(isLocalRedirect()).toBe(true);
  });

  it("falls back to the dev origin with no browser or configured origin", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "");
    setBrowserOrigin(null);
    expect(getSiteOrigin()).toBe(DEFAULT_SITE_ORIGIN);
  });

  it("rejects configured values with a path, query or non-HTTP scheme", () => {
    for (const value of [
      `${PRODUCTION_ORIGIN}/some/path`,
      `${PRODUCTION_ORIGIN}?x=1`,
      "ftp://files.example.test",
      "not a url",
    ]) {
      vi.stubEnv("NEXT_PUBLIC_SITE_URL", value);
      expect(getConfiguredSiteOrigin()).toBeNull();
    }
  });

  it("regression: a configured production origin never redirects to localhost", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", PRODUCTION_ORIGIN);
    setBrowserOrigin("http://localhost:3000");
    const redirect = getEmailRedirectTo();
    expect(redirect).not.toContain("localhost");
    expect(redirect).not.toContain("127.0.0.1");
    expect(redirect.startsWith(PRODUCTION_ORIGIN)).toBe(true);
    expect(isLocalRedirect()).toBe(false);
  });
});
