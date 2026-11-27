import type { Profile } from "@/types/auth";

/** Auth events that must never blank a cached, authenticated UI. */
export const SILENT_AUTH_EVENTS: ReadonlySet<string> = new Set([
  "INITIAL_SESSION",
  "SIGNED_IN",
  "TOKEN_REFRESHED",
  "USER_UPDATED",
]);

/**
 * True when a background refresh produced no authorization-relevant change.
 * Keeping the same object reference prevents dashboard data hooks from
 * refetching simply because the browser regained focus.
 */
export function profileUnchanged(
  current: Profile | null,
  next: Profile | null,
): boolean {
  if (!current || !next) return false;
  return (
    current.id === next.id &&
    current.role === next.role &&
    current.full_name === next.full_name &&
    current.phone === next.phone &&
    current.is_active === next.is_active &&
    current.updated_at === next.updated_at
  );
}

/**
 * A session event is silent only for the already-authenticated user. A new
 * identity, or a first load with no cached profile, always needs a full sync.
 */
export function shouldSilentlySync(
  event: string,
  activeUserId: string | null,
  sessionUserId: string,
  hasCachedProfile: boolean,
): boolean {
  return (
    hasCachedProfile &&
    activeUserId === sessionUserId &&
    SILENT_AUTH_EVENTS.has(event)
  );
}
