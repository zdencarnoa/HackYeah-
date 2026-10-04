"use client";

/**
 * The live event stream (C's GET /api/events). EventSource only delivers named
 * events to listeners added per name, so every name in LiveEventMap is subscribed.
 * The browser reconnects by itself (the backend sends `retry: 1000`); this wrapper
 * adds a connection state for the header and a de-duplication key so a replayed
 * event after a reconnect is not announced twice.
 */

import { useSyncExternalStore } from "react";

import { API_URL, LIVE } from "../api";
import type { LiveEventMap, LiveEventName } from "../contracts";

export type ConnectionState = "connecting" | "open" | "closed";

export type LiveHandler = <K extends LiveEventName>(name: K, payload: LiveEventMap[K]) => void;

const EVENT_NAMES: LiveEventName[] = [
  "message.scored",
  "incident.created",
  "incident.escalated",
  "incident.updated",
  "campaign.updated",
  "containment.done",
  "recovery.updated",
];

/** Fingerprint of an event, so an identical replay can be skipped. */
function fingerprint(name: string, raw: string): string {
  return `${name}:${raw}`;
}

export interface LiveConnection {
  close: () => void;
}

export function connectLiveEvents(
  onEvent: LiveHandler,
  onState: (state: ConnectionState) => void,
): LiveConnection {
  if (!LIVE || typeof EventSource === "undefined") {
    onState("closed");
    return { close: () => {} };
  }
  const seen = new Set<string>();
  const source = new EventSource(`${API_URL}/api/events`);
  onState("connecting");
  source.onopen = () => onState("open");
  source.onerror = () => onState(source.readyState === EventSource.CLOSED ? "closed" : "connecting");
  for (const name of EVENT_NAMES) {
    source.addEventListener(name, (event) => {
      const raw = (event as MessageEvent<string>).data;
      const key = fingerprint(name, raw);
      if (seen.has(key)) return;
      seen.add(key);
      if (seen.size > 500) seen.delete(seen.values().next().value as string);
      try {
        onEvent(name, JSON.parse(raw));
      } catch {
        // a malformed payload must not take the stream down
      }
    });
  }
  return { close: () => source.close() };
}

// One shared connection for the whole window: the header badge and the alert feed
// subscribe to it instead of each opening their own EventSource.
const handlers = new Set<LiveHandler>();
const stateListeners = new Set<() => void>();
let shared: LiveConnection | null = null;
let sharedState: ConnectionState = LIVE ? "connecting" : "closed";

function setSharedState(state: ConnectionState): void {
  sharedState = state;
  for (const listener of stateListeners) listener();
}

function retain(): void {
  if (shared || !LIVE) return;
  shared = connectLiveEvents((name, payload) => {
    for (const handler of handlers) handler(name, payload);
  }, setSharedState);
}

function release(): void {
  if (handlers.size > 0 || stateListeners.size > 0) return;
  shared?.close();
  shared = null;
  sharedState = LIVE ? "connecting" : "closed";
}

/** Subscribe to every live event. Returns the unsubscribe function. */
export function subscribeLiveEvents(handler: LiveHandler): () => void {
  handlers.add(handler);
  retain();
  return () => {
    handlers.delete(handler);
    release();
  };
}

function subscribeState(listener: () => void): () => void {
  stateListeners.add(listener);
  retain();
  return () => {
    stateListeners.delete(listener);
    release();
  };
}

/** Connection state for the header badge; always "closed" in mock mode. */
export function useLiveConnection(): ConnectionState {
  return useSyncExternalStore(
    subscribeState,
    () => sharedState,
    () => (LIVE ? "connecting" : "closed"),
  );
}
