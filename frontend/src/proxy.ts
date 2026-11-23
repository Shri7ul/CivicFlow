import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  hasSupabaseAuthCookie,
  isProtectedPath,
} from "@/lib/auth/routing";
import { isSupabaseConfigured } from "@/lib/supabase/config";

/**
 * Optimistic route protection only. The signed JWT is verified by the FastAPI
 * backend on every protected API request; this proxy just avoids rendering the
 * dashboard shell when no Supabase session cookie exists.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!isProtectedPath(pathname) || !isSupabaseConfigured()) {
    return NextResponse.next();
  }
  if (hasSupabaseAuthCookie(request.cookies.getAll())) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/incidents/:path*",
    "/map/:path*",
    "/risk/:path*",
    "/decisions/:path*",
  ],
};
