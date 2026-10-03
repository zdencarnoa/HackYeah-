"use client";

/**
 * The demo state shared by every open window in mock mode. Each change is saved to
 * localStorage and broadcast on a BroadcastChannel, so the employee window and the
 * admin window, side by side, show the same story within a moment. When C's live
 * event stream exists, the same actions become API calls (see lib/api.ts).
 */

import { useEffect, useState, useSyncExternalStore } from "react";

import type { ContainmentActionType, InteractionKind } from "../contracts";
import { EMAIL_BY_ID, ORG } from "../mocks";
import { containmentPlan, passwordEntryFor } from "./selectors";
import {
  NO_EFFECTS,
  UNUSUAL_SIGN_IN_DELAY_MS,
  initialState,
  mergeStates,
  newId,
  sameState,
  type ContainmentEffects,
  type DemoEvent,
  type DemoState,
} from "./state";

const STORAGE_KEY = "security-copilot-demo-v1";
const CHANNEL_NAME = "security-copilot-demo";
/** A fixed state for server rendering; every window replaces it right after mount. */
const SERVER_STATE: DemoState = {
  session: { id: "server", createdAt: 0, startedAt: null, speed: 4, updatedAt: 0 },
  events: {},
};

type Listener = () => void;

class DemoStore {
  private state: DemoState = SERVER_STATE;
  private listeners = new Set<Listener>();
  private channel: BroadcastChannel | null = null;
  private started = false;

  private start(): void {
    if (this.started || typeof window === "undefined") return;
    this.started = true;
    this.state = load() ?? initialState();
    save(this.state);
    try {
      this.channel = new BroadcastChannel(CHANNEL_NAME);
      this.channel.onmessage = (event: MessageEvent<DemoState>) => this.receive(event.data);
    } catch {
      this.channel = null; // very old browsers: the storage event below still syncs
    }
    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEY && event.newValue) this.receive(JSON.parse(event.newValue) as DemoState);
    });
  }

  subscribe = (listener: Listener): (() => void) => {
    this.start();
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): DemoState => {
    this.start();
    return this.state;
  };

  getServerSnapshot = (): DemoState => SERVER_STATE;

  update(change: (state: DemoState) => DemoState): void {
    this.start();
    this.state = change(this.state);
    save(this.state);
    this.channel?.postMessage(this.state);
    this.notify();
  }

  private receive(incoming: DemoState): void {
    const merged = mergeStates(this.state, incoming);
    if (sameState(merged, this.state)) return;
    this.state = merged;
    save(merged);
    if (!sameState(merged, incoming)) this.channel?.postMessage(merged); // the sender missed something
    this.notify();
  }

  private notify(): void {
    for (const listener of this.listeners) listener();
  }
}

function load(): DemoState | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DemoState) : null;
  } catch {
    return null;
  }
}

function save(state: DemoState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // private mode or storage full: the demo still runs in this window
  }
}

export const demoStore = new DemoStore();

// ------------------------------------------------------------------- hooks

export function useDemoState(): DemoState {
  return useSyncExternalStore(demoStore.subscribe, demoStore.getSnapshot, demoStore.getServerSnapshot);
}

/** The current time, refreshed every `intervalMs`, so scheduled deliveries appear. */
export function useNow(intervalMs = 500): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

// ----------------------------------------------------------------- actions

function addEvent(event: DemoEvent): void {
  demoStore.update((state) => ({ ...state, events: { ...state.events, [event.id]: event } }));
}

function updateSession(change: (session: DemoState["session"]) => Partial<DemoState["session"]>): void {
  demoStore.update((state) => ({
    ...state,
    session: { ...state.session, ...change(state.session), updatedAt: Date.now() },
  }));
}

export const demoActions = {
  /** D's attack engine: start delivering the campaign. */
  launchAttack(): void {
    updateSession((s) => (s.startedAt === null ? { startedAt: Date.now() } : {}));
  },

  setSpeed(speed: number): void {
    updateSession((s) => {
      if (s.startedAt === null) return { speed };
      // Keep the simulated clock where it is, so nothing already delivered disappears.
      const elapsedSimulated = (Date.now() - s.startedAt) * s.speed;
      return { speed, startedAt: Date.now() - elapsedSimulated / speed };
    });
  },

  /** Skip ahead `simulatedSeconds` of the attack script (rehearsals). */
  fastForward(simulatedSeconds: number): void {
    updateSession((s) => (s.startedAt === null ? {} : { startedAt: s.startedAt - (simulatedSeconds * 1000) / s.speed }));
  },

  /** D's POST /api/sim/reset: back to a calm inbox, in every window. */
  reset(): void {
    demoStore.update(() => initialState());
  },

  /** A click on a link in a delivered email, recorded before the page opens (A's /r/{token}). */
  recordClick(employeeId: string, messageId: string, url: string): void {
    addEvent({ id: newId("click"), kind: "link_clicked", at: Date.now(), employeeId, messageId, url, domain: hostOf(url) });
  },

  /**
   * A password typed on a sign-in page. Approved company domains never fire; any
   * other domain becomes a simulated Chrome PASSWORD_REUSE_EVENT, followed a few
   * seconds later by a simulated unusual sign-in. The password itself is never
   * passed in, stored or sent.
   */
  recordPasswordEntry(employeeId: string, url: string): "approved" | "reported" {
    const domain = hostOf(url);
    if (isApprovedLogin(domain)) return "approved";
    const now = Date.now();
    const state = demoStore.getSnapshot();
    const lastClick = Object.values(state.events)
      .filter((e): e is Extract<DemoEvent, { kind: "link_clicked" }> =>
        e.kind === "link_clicked" && e.employeeId === employeeId && e.domain === domain)
      .sort((a, b) => b.at - a.at)[0];
    const firstEntry = !passwordEntryFor(state, now, employeeId);
    addEvent({ id: newId("pwd"), kind: "password_reuse", at: now, employeeId, messageId: lastClick?.messageId ?? null, url, domain });
    if (firstEntry) {
      addEvent({
        id: newId("signin"), kind: "unusual_sign_in", at: now + UNUSUAL_SIGN_IN_DELAY_MS, employeeId,
        messageId: lastClick?.messageId ?? null, location: "Lagos, Nigeria", ip: "198.51.100.23",
      });
    }
    return "reported";
  },

  /** The employee's answer in the "What happened?" flow (C's POST /api/interactions). */
  reportInteraction(employeeId: string, messageId: string, interaction: InteractionKind): void {
    addEvent({ id: newId("report"), kind: "user_report", at: Date.now(), employeeId, messageId, interaction });
  },

  /**
   * Admin-approved containment (D's simulated actions). `actions` are run against
   * what has been delivered at this moment; everything is simulated.
   */
  approveContainment(campaignId: string | null, actions: ContainmentActionType[], approvedBy: string, messageId?: string): void {
    const now = Date.now();
    const state = demoStore.getSnapshot();
    // "contain_campaign" runs every action that still has something to do; actions
    // already fully applied keep their earlier result.
    const wanted = new Set(actions.includes("contain_campaign") ? undefined : actions);
    const plan = containmentPlan(state, now, campaignId, messageId)
      .filter((p) => (wanted.size === 0 || wanted.has(p.action)) && p.remaining > 0);
    if (plan.length === 0) return;
    const effects: ContainmentEffects = structuredClone(NO_EFFECTS);
    for (const p of plan) Object.assign(effects, mergeEffects(effects, p.effects));
    addEvent({
      id: newId("contain"), kind: "containment", at: now, approvedBy, campaignId: campaignId ?? messageId ?? null, effects,
      results: plan.map((p) => ({
        action: p.action, summary: p.summary, affected_count: p.details.length || 1, details: p.details,
        at: new Date(now).toISOString(), simulated: true as const,
      })),
    });
  },

  /** Ticks or unticks an incident checklist item (id from checklistItemIds()). */
  setChecklistItem(itemId: string, done: boolean): void {
    addEvent({ id: newId("check"), kind: "checklist", at: Date.now(), itemId, done });
  },
};

function mergeEffects(base: ContainmentEffects, extra: Partial<ContainmentEffects>): ContainmentEffects {
  const out = { ...base };
  for (const [key, value] of Object.entries(extra) as [keyof ContainmentEffects, unknown][]) {
    if (key === "investigationStarted") out.investigationStarted ||= Boolean(value);
    else out[key] = [...new Set([...(out[key] as string[]), ...(value as string[])])];
  }
  return out;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/\.$/, "");
  } catch {
    return "";
  }
}

/** True for the company's own sign-in pages (D's ApprovedLogins). */
export function isApprovedLogin(domain: string): boolean {
  return ORG.approved_logins.some((a) => domain === a.domain || domain.endsWith(`.${a.domain}`));
}

export function emailSubject(messageId: string): string {
  return EMAIL_BY_ID[messageId]?.message.subject ?? messageId;
}
