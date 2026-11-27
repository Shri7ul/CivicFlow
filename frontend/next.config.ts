import type { NextConfig } from "next";

/**
 * Baseline browser security headers (Phase 13).
 *
 * These are conservative defaults for a Next.js App Router application that
 * renders MapLibre tiles and talks to a separate FastAPI origin. They are not
 * a substitute for server-side authorization: the backend remains
 * authoritative for every data and geographic scope decision.
 */
function apiOrigin(): string | null {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

function supabaseOrigins(): string[] {
  const defaults = ["https://*.supabase.co", "wss://*.supabase.co"];
  const value = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!value) return defaults;
  try {
    const httpOrigin = new URL(value).origin;
    const wsOrigin = httpOrigin.replace(/^http/, "ws");
    // A self-hosted or local Supabase must be permitted by CSP as well,
    // otherwise signup/login silently fail with "Failed to fetch".
    return [...new Set([httpOrigin, wsOrigin, ...defaults])];
  } catch {
    return defaults;
  }
}

const supabaseSources = supabaseOrigins();

const tileSources = [
  "https://a.basemaps.cartocdn.com",
  "https://b.basemaps.cartocdn.com",
  "https://c.basemaps.cartocdn.com",
  "https://server.arcgisonline.com",
  "https://services.arcgisonline.com",
];

const connectSources = [
  "'self'",
  apiOrigin(),
  ...supabaseSources,
  // MapLibre fetches glyph PBFs with fetch(), which is governed by
  // connect-src (not font-src). Without this origin all map text labels fail.
  "https://fonts.openmaptiles.org",
  // Reverse geocoding in the incident location picker.
  "https://nominatim.openstreetmap.org",
  ...tileSources,
].filter((item): item is string => Boolean(item));

const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${tileSources.join(" ")} ${supabaseSources.filter((s) => s.startsWith("http:") || s.startsWith("https:")).join(" ")}`,
  `connect-src ${connectSources.join(" ")}`,
  "font-src 'self' data: https://fonts.openmaptiles.org",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  {
    key: "Permissions-Policy",
    // geolocation=(self) is required by the incident locator and the map's
    // "use my location" control. Keeping it empty made both features unusable.
    value: "camera=(), microphone=(), geolocation=(self), payment=()",
  },
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  reactCompiler: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
