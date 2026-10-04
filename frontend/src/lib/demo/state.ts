/**
 * The shared demo state in mock mode: a session (when the attack was launched, how
 * fast it plays) plus an append-only log of what people did. Everything shown on
 * screen is derived from this (see selectors.ts), so two browser windows that share
 * the same state always show the same story.
 */

import type { ContainmentResult, InteractionKind } from "../contracts";

export interface Session {
  id: string;
  createdAt: number;
  /** Epoch ms when "Launch attack" was pressed; null before. */
  startedAt: number | null;
  /** Delivery speed: 4 means four simulated seconds per real second. */
  speed: number;
  updatedAt: number;
}

interface EventBase {
  id: string;
  /** Epoch ms. Events may be scheduled in the future (the unusual sign-in). */
  at: number;
}

export type DemoEvent =
  | (EventBase & { kind: "link_clicked"; employeeId: string; messageId: string; url: string; domain: string })
  | (EventBase & { kind: "password_reuse"; employeeId: string; messageId: string | null; url: string; domain: string })
  | (EventBase & { kind: "unusual_sign_in"; employeeId: string; messageId: string | null; location: string; ip: string })
  | (EventBase & { kind: "user_report"; employeeId: string; messageId: string; interaction: InteractionKind })
  | (EventBase & {
      kind: "containment";
      approvedBy: string;
      campaignId: string | null;
      results: ContainmentResult[];
      effects: ContainmentEffects;
    })
  | (EventBase & { kind: "checklist"; itemId: string; done: boolean });

export type DemoEventKind = DemoEvent["kind"];

/** What an approved containment action changed in the simulated organization. */
export interface ContainmentEffects {
  quarantinedMessageIds: string[];
  blockedSenders: string[];
  blockedDomains: string[];
  notifiedEmployeeIds: string[];
  revokedEmployeeIds: string[];
  resetEmployeeIds: string[];
  disabledEmployeeIds: string[];
  investigationStarted: boolean;
}

export const NO_EFFECTS: ContainmentEffects = {
  quarantinedMessageIds: [],
  blockedSenders: [],
  blockedDomains: [],
  notifiedEmployeeIds: [],
  revokedEmployeeIds: [],
  resetEmployeeIds: [],
  disabledEmployeeIds: [],
  investigationStarted: false,
};

export interface DemoState {
  session: Session;
  events: Record<string, DemoEvent>;
}

/** Demo speed when the attack is launched: the 12-minute script plays in about 3 minutes. */
export const DEFAULT_SPEED = 4;
/** Offset of the first attack email; earlier mail is already in the inbox at reset. */
export const ATTACK_FIRST_OFFSET_S = 120;
/** Delay between "Launch attack" and the first attack email landing. */
export const FIRST_DELIVERY_DELAY_MS = 2000;
/** The simulated unusual sign-in follows a password entry after this long. */
export const UNUSUAL_SIGN_IN_DELAY_MS = 5000;

export function newId(prefix: string): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(16).slice(2, 10);
  return `${prefix}-${random}`;
}

export function initialState(now = Date.now()): DemoState {
  return {
    session: { id: newId("session"), createdAt: now, startedAt: null, speed: DEFAULT_SPEED, updatedAt: now },
    events: {},
  };
}

/**
 * Combines the state of two windows: a newer reset wins outright; otherwise the
 * event logs are united and the later session settings win. Merging never loses
 * an event, even when both windows act at the same moment.
 */
export function mergeStates(a: DemoState, b: DemoState): DemoState {
  if (a.session.id !== b.session.id) {
    return a.session.createdAt >= b.session.createdAt ? a : b;
  }
  const session = a.session.updatedAt >= b.session.updatedAt ? a.session : b.session;
  return { session, events: { ...b.events, ...a.events } };
}

export function sameState(a: DemoState, b: DemoState): boolean {
  if (a.session.id !== b.session.id || a.session.updatedAt !== b.session.updatedAt) return false;
  const aKeys = Object.keys(a.events);
  return aKeys.length === Object.keys(b.events).length && aKeys.every((k) => k in b.events);
}

/** Events that have happened by `now`, oldest first. */
export function pastEvents(state: DemoState, now: number): DemoEvent[] {
  return Object.values(state.events)
    .filter((e) => e.at <= now)
    .sort((x, y) => x.at - y.at || x.id.localeCompare(y.id));
}
