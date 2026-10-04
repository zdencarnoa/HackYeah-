"use client";

/**
 * Live incidents and campaigns: loaded once from C's REST endpoints, then kept
 * current by the SSE events. The backend has no list-all-messages endpoint, so the
 * live console is organized around incidents and campaigns, which it does have.
 */

import { useSyncExternalStore } from "react";

import { LIVE, liveApi } from "../api";
import type { Campaign, Incident } from "../contracts";
import { subscribeLiveEvents } from "./events";

export interface LiveIncidents {
  incidents: Incident[];
  campaigns: Campaign[];
  /** True once the first load finished, whether or not it worked. */
  loaded: boolean;
  error: string | null;
}

const EMPTY: LiveIncidents = { incidents: [], campaigns: [], loaded: false, error: null };
let snapshot: LiveIncidents = EMPTY;
const listeners = new Set<() => void>();
let unsubscribe: (() => void) | null = null;

function set(next: Partial<LiveIncidents>): void {
  snapshot = { ...snapshot, ...next };
  for (const listener of listeners) listener();
}

function upsert<T extends { id: string }>(items: T[], item: T): T[] {
  return items.some((existing) => existing.id === item.id)
    ? items.map((existing) => (existing.id === item.id ? item : existing))
    : [item, ...items];
}

/** Most severe first, then newest. */
export function sortIncidents(incidents: Incident[]): Incident[] {
  return incidents.slice().sort((a, b) => b.severity - a.severity || b.created_at.localeCompare(a.created_at));
}

export async function refreshLiveIncidents(): Promise<void> {
  const [incidents, campaigns] = await Promise.all([liveApi.incidents(), liveApi.campaigns()]);
  if (incidents.ok && campaigns.ok) {
    set({ incidents: incidents.data, campaigns: campaigns.data, loaded: true, error: null });
  } else {
    const failed = !incidents.ok ? incidents : (campaigns as { ok: false; error: string });
    set({ loaded: true, error: failed.ok ? null : failed.error });
  }
}

function start(): void {
  if (unsubscribe || !LIVE) return;
  void refreshLiveIncidents();
  unsubscribe = subscribeLiveEvents((name, payload) => {
    if (name === "incident.created" || name === "incident.escalated" || name === "incident.updated") {
      set({ incidents: upsert(snapshot.incidents, payload as Incident) });
    } else if (name === "campaign.updated") {
      set({ campaigns: upsert(snapshot.campaigns, payload as Campaign) });
    }
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  start();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      unsubscribe?.();
      unsubscribe = null;
    }
  };
}

export function useLiveIncidents(): LiveIncidents {
  return useSyncExternalStore(subscribe, () => snapshot, () => EMPTY);
}

/** A demo reset empties the list, then reloads what the backend now has. */
export function resetLiveIncidents(): void {
  snapshot = EMPTY;
  for (const listener of listeners) listener();
  void refreshLiveIncidents();
}
