const DEFAULT_SUPABASE_URL = "";
const DEFAULT_SUPABASE_ANON_KEY = "";

export type SupabaseBrowserConfig = {
  url: string;
  anonKey: string;
};

function readEnv(value: string | undefined, fallback: string): string {
  return (value ?? fallback).trim();
}

export function getSupabaseBrowserConfig(): SupabaseBrowserConfig {
  return {
    url: readEnv(process.env.NEXT_PUBLIC_SUPABASE_URL, DEFAULT_SUPABASE_URL).replace(
      /\/+$/,
      "",
    ),
    anonKey: readEnv(
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      DEFAULT_SUPABASE_ANON_KEY,
    ),
  };
}

export function isSupabaseConfigured(
  config: SupabaseBrowserConfig = getSupabaseBrowserConfig(),
): boolean {
  return (
    /^https?:\/\/[^/\s]+/i.test(config.url) &&
    config.anonKey.length > 20 &&
    !config.anonKey.toLowerCase().includes("service_role")
  );
}
