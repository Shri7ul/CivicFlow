import { safeNextPath } from "@/lib/auth/routing";

export type CallbackParameters = {
  code: string | null;
  errorDescription: string | null;
  next: string;
};

/**
 * Parse the PKCE callback query string. The authorization code is returned to
 * the caller for a single exchange and is never included in messages or logs.
 */
export function readCallbackParameters(search: string): CallbackParameters {
  const params = new URLSearchParams(search);
  const rawCode = params.get("code");
  return {
    code: rawCode && rawCode.trim().length > 0 ? rawCode.trim() : null,
    errorDescription: params.get("error_description"),
    next: safeNextPath(params.get("next")),
  };
}
