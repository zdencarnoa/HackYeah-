/**
 * The one place that talks to the backend. With NEXT_PUBLIC_API_URL unset the UI
 * runs on mocks (lib/mocks.ts + lib/demo/*); set it to the FastAPI address
 * (e.g. http://localhost:8000) to use the live API as each endpoint lands.
 */

import type { Assessment, Message } from "./contracts";
import { DEMO_EMPLOYEE_ID, EMAIL_BY_ID } from "./mocks";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const LIVE = API_URL !== "";

export type AnalyzeResult =
  | { ok: true; assessment: Assessment; message: Message | null }
  | { ok: false; error: string };

/**
 * "Is this safe?" for an uploaded .eml: B's POST /api/analyze. In mock mode only
 * the demo emails can be checked (exported by `python -m app.detection.export_eml`),
 * recognized by their Message-ID header.
 */
export async function analyzeEmlFile(file: File): Promise<AnalyzeResult> {
  if (LIVE) {
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${API_URL}/api/analyze`, { method: "POST", body });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        return { ok: false, error: detail?.detail ?? `The check failed (${response.status}).` };
      }
      return { ok: true, assessment: (await response.json()) as Assessment, message: null };
    } catch {
      return { ok: false, error: "We could not reach Security Copilot. Check that the backend is running." };
    }
  }
  const text = await file.slice(0, 64 * 1024).text();
  if (!/^(from|to|subject|date|message-id|received)\s*:/im.test(text)) {
    return { ok: false, error: "This file is not an email. Save the email as an .eml file and try again." };
  }
  const messageId = /^message-id:\s*<([^@>\s]+)@/im.exec(text)?.[1];
  const known = messageId ? EMAIL_BY_ID[messageId] : undefined;
  if (!known) {
    return {
      ok: false,
      error: "In demo mode only the demo emails can be checked. Start the backend to check any other email.",
    };
  }
  return { ok: true, assessment: known.assessment, message: known.message };
}

/**
 * Where a clicked link opens. Live: A's rewritten /r/{token} link already points
 * at the backend. Mock: the simulated page for the original address, served by
 * this app at /demo/{host}/{path}. Only reserved .example/.test domains get a page.
 * Pass the employee for anyone but Alice, so the page knows who typed a password.
 */
export function demoPageFor(url: string, employeeId?: string): string | null {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/\.$/, "");
    if (!host.endsWith(".example") && !host.endsWith(".test")) return null;
    if (employeeId && employeeId !== DEMO_EMPLOYEE_ID) parsed.searchParams.set("as", employeeId);
    return `/demo/${host}${parsed.pathname === "/" ? "" : parsed.pathname}${parsed.search}`;
  } catch {
    return null;
  }
}
