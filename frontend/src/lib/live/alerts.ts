"use client";

/**
 * Live admin alerts, built from C's incident events. A HIGH or CRITICAL incident
 * (created or escalated) becomes one alert; a rise in severity is a new alert, so
 * the banner, sound and notification fire again when "clicked" becomes "entered a
 * password". Plain updates at the same severity add nothing.
 */

import { useSyncExternalStore } from "react";

import { Severity, type Incident } from "../contracts";
import type { Alert } from "../demo/selectors";
import { EMPLOYEE_BY_ID } from "../mocks";
import { subscribeLiveEvents } from "./events";

let alerts: Alert[] = [];
const listeners = new Set<() => void>();
let unsubscribe: (() => void) | null = null;

function emit(next: Alert[]): void {
  alerts = next;
  for (const listener of listeners) listener();
}

/** The alert for an incident, or null when it is below HIGH. */
export function alertFromIncident(incident: Incident, at = Date.now()): Alert | null {
  if (incident.severity < Severity.HIGH) return null;
  const latest = incident.timeline[incident.timeline.length - 1];
  const employeeId = latest?.employee_id ?? incident.affected_employees[0];
  const name = EMPLOYEE_BY_ID[employeeId]?.name ?? "An employee";
  const critical = incident.severity >= Severity.CRITICAL;
  const campaignHint = incident.campaign_id ? " It is part of a wider campaign." : "";
  return {
    key: `incident:${incident.id}:${incident.severity}`,
    severity: incident.severity,
    title: critical ? `Likely account compromise: ${name}` : `Possible exposure: ${name}`,
    body: `${latest?.text ?? "New evidence was recorded."}${campaignHint}`,
    at,
    employeeId,
    messageId: incident.evidence.find((e) => e.message_id)?.message_id ?? undefined,
    campaignId: incident.campaign_id ?? undefined,
  };
}

function start(): void {
  if (unsubscribe) return;
  unsubscribe = subscribeLiveEvents((name, payload) => {
    if (name !== "incident.created" && name !== "incident.escalated") return;
    const alert = alertFromIncident(payload as Incident);
    if (alert && !alerts.some((existing) => existing.key === alert.key)) emit([alert, ...alerts]);
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

/** Newest first. Empty in mock mode. */
export function useLiveAlerts(): Alert[] {
  return useSyncExternalStore(subscribe, () => alerts, () => alerts);
}

/** A demo reset clears the alert history. */
export function clearLiveAlerts(): void {
  emit([]);
}
