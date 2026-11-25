import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import { authorizationHeader, requireAccessToken } from "./session";

describe("authenticated request token handling", () => {
  it("returns a valid access token", () => {
    expect(requireAccessToken("access-token-123")).toBe("access-token-123");
  });

  it("fails with 401 when the token is missing", () => {
    expect(() => requireAccessToken(null)).toThrowError(ApiError);
    expect(() => requireAccessToken(null)).toThrowError(
      "Your session has expired. Please sign in again.",
    );
    try {
      requireAccessToken(undefined);
    } catch (error) {
      expect(error).toMatchObject({ status: 401, code: "not_authenticated" });
    }
  });

  it("fails with 401 for an expired/empty session token", () => {
    expect(() => requireAccessToken("")).toThrowError(ApiError);
    expect(() => requireAccessToken("   ")).toThrowError(ApiError);
  });

  it("builds a bearer Authorization header", () => {
    expect(authorizationHeader("abc")).toEqual({ Authorization: "Bearer abc" });
  });
});
