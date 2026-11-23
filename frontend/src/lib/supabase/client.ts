"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import {
  getSupabaseBrowserConfig,
  isSupabaseConfigured,
} from "@/lib/supabase/config";

let browserClient: SupabaseClient | null = null;

/**
 * Returns a singleton browser client, or null when public Supabase
 * configuration is absent. The service-role key must never reach the browser.
 */
export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (!isSupabaseConfigured()) {
    return null;
  }
  if (browserClient) {
    return browserClient;
  }
  const { url, anonKey } = getSupabaseBrowserConfig();
  browserClient = createBrowserClient(url, anonKey, {
    auth: {
      flowType: "pkce",
      detectSessionInUrl: true,
      persistSession: true,
      autoRefreshToken: true,
    },
  });
  return browserClient;
}

export function resetSupabaseBrowserClientForTests(): void {
  browserClient = null;
}
