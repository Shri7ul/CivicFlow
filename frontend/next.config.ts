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

const connectSources = [
  "'self'",
  apiOrigin(),
  "https://*.supabase.co",
  "wss://*.supabase.co",
].filter((item): item is string => Boolean(item));

const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://tile.openstreetmap.org https://*.supabase.co",
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
    value: "camera=(), microphone=(), geolocation=(), payment=()",
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
