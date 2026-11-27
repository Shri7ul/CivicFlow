import type { ProfileRole } from "@/types/auth";

const DASHBOARD_PREFIX = "/dashboard";
const INCIDENTS_PREFIX = "/incidents";
const MAP_PATH = "/map";
const RISK_PATH = "/risk";
const DECISIONS_PATH = "/decisions";
const OPERATIONS_PATH = "/operations";
const VALIDATION_PATH = "/validation";
const PILOT_PATH = "/pilot";
const ADMIN_PATH = "/admin";
const WORKER_PATH = "/worker";
const WORKFORCE_PREFIX = "/workforce";
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
  ADMIN_PATH,
  WORKER_PATH,
  WORKFORCE_PREFIX,
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

/**
 * Navigation paths a role can actually use. This is UX only: the backend
 * independently enforces every permission. Each operational surface is
 * reachable only by the role that owns it.
 */
export function navigationForRole(role: ProfileRole): readonly string[] {
  switch (role) {
    case "ADMIN":
      return [
        ADMIN_PATH,
        OPERATIONS_PATH,
        INCIDENTS_PREFIX,
        RISK_PATH,
        DECISIONS_PATH,
        VALIDATION_PATH,
        PILOT_PATH,
      ];
    case "WORKER":
      return [
        WORKER_PATH,
        INCIDENTS_PREFIX,
        MAP_PATH,
        RISK_PATH,
        `${WORKFORCE_PREFIX}/status`,
      ];
    default:
      return [
        DASHBOARD_PREFIX,
        INCIDENTS_PREFIX,
        MAP_PATH,
        RISK_PATH,
        `${WORKFORCE_PREFIX}/apply`,
        `${WORKFORCE_PREFIX}/status`,
      ];
  }
}

export function canAccessPath(role: ProfileRole, pathname: string): boolean {
  return navigationForRole(role).some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/** Landing page for each role after login or a failed route guard. */
export function homePathForRole(role: ProfileRole): string {
  if (role === "ADMIN") return ADMIN_PATH;
  if (role === "WORKER") return WORKER_PATH;
  return DASHBOARD_PREFIX;
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
