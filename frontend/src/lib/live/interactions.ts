/**
 * Live mode: send Alice's click and password entry to the backend too, so C opens the
 * real incidents (HIGH on the click, CRITICAL on the password). The employee window
 * keeps its own pages; this only reports what happened through D's tracked links:
 * GET /r/{token} records the click, POST /r/{token}/submit records a typed password
 * (the password itself is never sent, only `entered=1`).
 */

import { API_URL, liveApi } from "../api";

/** The tracked link the engine made for this employee, message and address. */
async function tokenFor(employeeId: string, messageId: string, url?: string): Promise<string | null> {
  const inbox = await liveApi.inbox(employeeId);
  if (!inbox.ok) return null;
  const links = inbox.data.find((m) => m.id === messageId)?.links ?? [];
  return (links.find((l) => l.url === url) ?? links[0])?.token ?? null;
}

export async function reportLiveClick(employeeId: string, messageId: string, url: string): Promise<void> {
  const token = await tokenFor(employeeId, messageId, url);
  if (!token) return;
  await fetch(`${API_URL}/r/${encodeURIComponent(token)}`, { redirect: "manual" }).catch(() => undefined);
}

export async function reportLivePassword(employeeId: string, messageId: string | null): Promise<void> {
  if (!messageId) return;
  const token = await tokenFor(employeeId, messageId);
  if (!token) return;
  await fetch(`${API_URL}/r/${encodeURIComponent(token)}/submit`, {
    method: "POST",
    body: new URLSearchParams({ entered: "1" }),
  }).catch(() => undefined);
}
