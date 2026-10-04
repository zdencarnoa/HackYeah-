/**
 * The one place that talks to the backend. With NEXT_PUBLIC_API_URL unset the UI
 * runs on mocks (lib/mocks.ts + lib/demo/*); set it to the FastAPI address
 * (e.g. http://localhost:8000) to use the live API as each endpoint lands.
 */

import type {
  Assessment,
  AttackStatus,
  BlastRadius,
  Campaign,
  ContainmentRequest,
  ContainmentResult,
  InboxMessage,
  Incident,
  InteractionKind,
  InteractionResult,
  Message,
  RecoveryStatus,
} from "./contracts";
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

// ------------------------------------------------------------------ live API

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string; status: number | null };

const UNREACHABLE = "We could not reach Security Copilot. Check that the backend is running.";

/**
 * One typed call to the backend. Never throws: a failure becomes `{ ok: false }` with
 * a sentence a person can read, so a screen can show "live data unavailable" instead
 * of going blank. In mock mode every call fails the same way and callers use mocks.
 */
async function call<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  if (!LIVE) return { ok: false, error: "Live mode is off (NEXT_PUBLIC_API_URL is not set).", status: null };
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      const text = typeof detail?.detail === "string" ? detail.detail : `The request failed (${response.status}).`;
      return { ok: false, error: text, status: response.status };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: UNREACHABLE, status: null };
  }
}

const post = (body?: unknown): RequestInit => ({ method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const liveApi = {
  incidents: () => call<Incident[]>("/api/incidents"),
  incident: (id: string) => call<Incident>(`/api/incidents/${encodeURIComponent(id)}`),
  campaigns: () => call<Campaign[]>("/api/campaigns"),
  campaign: (id: string) => call<Campaign>(`/api/campaigns/${encodeURIComponent(id)}`),

  /** C's decision flow: what the employee says happened. */
  interact: (employeeId: string, messageId: string, kind: InteractionKind) =>
    call<InteractionResult>("/api/interactions", post({ employee_id: employeeId, message_id: messageId, kind })),

  /** D's attack engine. */
  launchAttack: (scenario = "microsoft", speed = 4) =>
    call<AttackStatus>(`/api/sim/attack/${encodeURIComponent(scenario)}?speed=${speed}`, post()),
  pauseAttack: () => call<AttackStatus>("/api/sim/attack/control/pause", post()),
  stepAttack: () => call<AttackStatus>("/api/sim/attack/control/step", post()),
  attackStatus: () => call<AttackStatus>("/api/sim/attack/status"),
  inbox: (employeeId: string) => call<InboxMessage[]>(`/api/sim/inbox/${encodeURIComponent(employeeId)}`),

  /** Simulated blast radius. Note: not under /sim. */
  blastRadius: (employeeId: string) => call<BlastRadius>(`/api/blast-radius/${encodeURIComponent(employeeId)}`),

  /** Admin-approved, simulated containment. */
  contain: (request: ContainmentRequest) => call<ContainmentResult[]>("/api/sim/containment", post(request)),
  recovery: () => call<RecoveryStatus>("/api/sim/recovery"),
  completeRecoveryItem: (itemId: string) =>
    call<RecoveryStatus>(`/api/sim/recovery/${encodeURIComponent(itemId)}/done`, post()),

  /**
   * Back to a calm demo. D's /api/sim/reset already resets the simulation, C's database
   * and A's links, and re-seeds D's organization. (C's old /api/dev/reset-and-seed must
   * not follow it: it re-seeds a placeholder org, so later deliveries find no recipient.)
   */
  async reset(): Promise<ApiResult<{ ok: true }>> {
    const sim = await call<AttackStatus>("/api/sim/reset", post());
    return sim.ok ? { ok: true, data: { ok: true } } : sim;
  },

  /** B's verdict for every demo email, keyed by message id (ML + rules + LLM text). */
  assessments: () => call<Record<string, Assessment>>("/api/assessments"),
};
