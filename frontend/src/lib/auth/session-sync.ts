import type { Profile } from "@/types/auth";

/** Auth events that must never blank a cached, authenticated UI. */
export const SILENT_AUTH_EVENTS: ReadonlySet<string> = new Set([
  "INITIAL_SESSION",
  "SIGNED_IN",
  "TOKEN_REFRESHED",
  "USER_UPDATED",
]);

/** Events that really do end the session (as opposed to a background sync). */
const SESSION_END_EVENTS: ReadonlySet<string> = new Set([
  "SIGNED_OUT",
  "USER_DELETED",
]);

/**
 * True when a background refresh produced no authorization-relevant change.
 *
 * Only identity and permission fields are compared. `updated_at`, `full_name`
 * and `phone` are deliberately ignored: Supabase re-emits auth events on every
 * tab focus, and a cosmetic timestamp or formatting difference must not swap
 * the profile object (which would remount the dashboard and refetch its data).
 * Real profile edits are still picked up on the next explicit full sync.
 */
export function profileUnchanged(
  current: Profile | null,
  next: Profile | null,
): boolean {
  if (!current || !next) return false;
  return (
    current.id === next.id &&
    current.role === next.role &&
    current.is_active === next.is_active
  );
}

/**
 * A session event is silent whenever we already hold a profile for this exact
 * user. Supabase's own visibility handler emits several event names on tab
 * focus (and libraries may add more), so gating only on a fixed event list can
 * still blank the UI. Only a genuine sign-out/identity change needs a full sync.
 */
export function shouldSilentlySync(
  event: string,
  activeUserId: string | null,
  sessionUserId: string,
  hasCachedProfile: boolean,
): boolean {
  if (SESSION_END_EVENTS.has(event)) return false;
  return hasCachedProfile && activeUserId === sessionUserId;
}
