/**
 * Site origin selection for Supabase email verification redirects.
 *
 * The redirect origin must be explicit in production so a deployment cannot
 * silently inherit localhost from a browser or from Supabase's default Site
 * URL. No production hostname is hardcoded here: operators set
 * NEXT_PUBLIC_SITE_URL to the deployed frontend origin.
 */

export const AUTH_CALLBACK_PATH = "/auth/callback";
export const DEFAULT_SITE_ORIGIN = "http://localhost:3000";

/** Return the explicitly configured site origin, or null when unset/invalid. */
export function getConfiguredSiteOrigin(): string | null {
  const value = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!value) {
    return null;
  }
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    // Only an origin is valid; paths/query/fragments belong on the callback.
    if (value.replace(/\/+$/, "") !== parsed.origin) {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

/** Browser origin, when code runs in a browser. */
export function getBrowserOrigin(): string | null {
  if (typeof window === "undefined" || !window.location?.origin) {
    return null;
  }
  return window.location.origin;
}

/** Effective frontend origin: explicit config, then browser, then dev default. */
export function getSiteOrigin(): string {
  return (
    getConfiguredSiteOrigin() ?? getBrowserOrigin() ?? DEFAULT_SITE_ORIGIN
  );
}

/** Full URL passed to Supabase as emailRedirectTo for sign-up verification. */
export function getEmailRedirectTo(path: string = AUTH_CALLBACK_PATH): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${getSiteOrigin()}${suffix}`;
}

/**
 * True when the effective redirect points at a local development origin.
 * Used by tests and diagnostics, never to weaken verification security.
 */
export function isLocalRedirect(origin: string = getSiteOrigin()): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin);
}
