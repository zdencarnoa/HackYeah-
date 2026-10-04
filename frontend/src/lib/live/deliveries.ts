/**
 * Live mode: which demo emails D's attack engine has delivered. The engine delivers
 * D's emails in deliver_offset_s order, the same order as EMAILS, so the first
 * `delivered_count` of them are in the inboxes. Each is stamped with the time this
 * window first saw it, so "newest first" and the warning banners behave as in mock mode.
 */

import type { AttackStatus } from "../contracts";
import { EMAILS } from "../mocks";

const seenAt = new Map<string, number>();
let deliveredCount = 0;

/** Applies a status poll: "reset" when the engine went back to the start, "changed" on new mail. */
export function syncDeliveries(status: AttackStatus): "reset" | "changed" | "same" {
  const count = Math.min(status.delivered_count, EMAILS.length);
  if (count === deliveredCount) return "same";
  const reset = count < deliveredCount;
  if (reset) seenAt.clear();
  const now = Date.now();
  EMAILS.slice(0, count).forEach((email, i) => {
    if (!seenAt.has(email.id)) seenAt.set(email.id, now + i); // +i keeps delivery order
  });
  deliveredCount = count;
  return reset ? "reset" : "changed";
}

/** When this window saw the email arrive, or null when the engine has not delivered it. */
export function liveDeliveryTime(emailId: string): number | null {
  return seenAt.get(emailId) ?? null;
}
