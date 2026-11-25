import type { ProfileRole } from "@/types/auth";

const DASHBOARD_PREFIX = "/dashboard";
const INCIDENTS_PREFIX = "/incidents";
const MAP_PATH = "/map";
const RISK_PATH = "/risk";
const DECISIONS_PATH = "/decisions";
const OPERATIONS_PATH = "/operations";
const VALIDATION_PATH = "/validation";
const PILOT_PATH = "/pilot";
const LOGIN_PATH = "/login";
const PROTECTED_PREFIXES = [
  DASHBOARD_PREFIX,
  INCIDENTS_PREFIX,
  MAP_PATH,
  RISK_PATH,
  DECISIONS_PATH,
  OPERATIONS_PATH,
  VALIDATION_PATH,
  PILOT_PATH,
] as const;

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function safeNextPath(value: string | null | undefined): string {
  if (!value) {
    return DASHBOARD_PREFIX;
  }
  const trimmed = value.trim();
  if (
    !trimmed.startsWith("/") ||
    trimmed.startsWith("//") ||
    trimmed.includes("\\") ||
    trimmed.startsWith("/login") ||
    trimmed.startsWith("/signup") ||
    trimmed.startsWith("/auth")
  ) {
    return DASHBOARD_PREFIX;
  }
  return trimmed;
}

export function buildLoginHref(nextPath?: string | null): string {
  const next = safeNextPath(nextPath);
  return next === DASHBOARD_PREFIX
    ? LOGIN_PATH
    : `${LOGIN_PATH}?next=${encodeURIComponent(next)}`;
}

type CookieLike = { name: string };

/**
 * Optimistic cookie presence check for the Next.js proxy only.
 * It is not authentication or authorization; the backend verifies every JWT.
 */
export function hasSupabaseAuthCookie(cookies: readonly CookieLike[]): boolean {
  return cookies.some(({ name }) => {
    const base = name.replace(/\.\d+$/, "");
    return /^sb-.*-auth-token$/.test(base);
  });
}

export function roleLabel(role: ProfileRole): string {
  switch (role) {
    case "ADMIN":
      return "Administrator";
    case "WORKER":
      return "Field worker";
    default:
      return "Citizen";
  }
}
