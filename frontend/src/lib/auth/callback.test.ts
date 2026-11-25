import { describe, expect, it } from "vitest";

import { readCallbackParameters } from "./callback";

describe("PKCE callback parameters", () => {
  it("extracts the authorization code and a safe next path", () => {
    const result = readCallbackParameters("?code=pkce-code-123&next=%2Fincidents");
    expect(result.code).toBe("pkce-code-123");
    expect(result.next).toBe("/incidents");
    expect(result.errorDescription).toBeNull();
  });

  it("defaults to the dashboard when no next path is supplied", () => {
    expect(readCallbackParameters("?code=abc").next).toBe("/dashboard");
  });

  it("surfaces provider error descriptions without a code", () => {
    const result = readCallbackParameters(
      "?error_description=Email+link+expired",
    );
    expect(result.code).toBeNull();
    expect(result.errorDescription).toBe("Email link expired");
  });

  it("never includes the authorization code in an error message", () => {
    const result = readCallbackParameters("?code=super-secret-code");
    expect(`${result.errorDescription ?? ""} ${result.next}`).not.toContain(
      "super-secret-code",
    );
  });

  it("rejects external next paths to prevent open redirects", () => {
    expect(readCallbackParameters("?code=abc&next=https%3A%2F%2Fevil.test").next).toBe(
      "/dashboard",
    );
  });
});
