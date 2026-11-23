import type { AuthStatus } from "@/types/auth";

export type AuthStateInput = {
  configured: boolean;
  sessionPresent: boolean;
  profilePresent: boolean;
  error?: string | null;
};

export function deriveAuthStatus(input: AuthStateInput): AuthStatus {
  if (!input.configured) {
    return "unconfigured";
  }
  if (input.error) {
    return "error";
  }
  if (!input.sessionPresent) {
    return "unauthenticated";
  }
  return input.profilePresent ? "authenticated" : "loading";
}

export function isAuthReady(status: AuthStatus): boolean {
  return status === "authenticated" || status === "unauthenticated" || status === "unconfigured";
}
