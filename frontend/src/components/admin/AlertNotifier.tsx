"use client";

/**
 * Browser notifications and a short sound for new HIGH and CRITICAL alerts, so the
 * admin notices demo step 4 even when looking elsewhere. Alerts that already
 * existed when the page opened never fire; only new ones do.
 */

import { useEffect, useRef } from "react";

import { SEVERITY_NAMES, Severity } from "@/lib/contracts";
import type { Alert } from "@/lib/demo/selectors";

let audio: AudioContext | null = null;

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  audio ??= new Ctor();
  if (audio.state === "suspended") void audio.resume();
  return audio;
}

/** Browsers only play sound after a click on the page; call this from one. */
export function unlockAlertSound(): void {
  audioContext();
}

/** One tone for HIGH, a two-tone siren for CRITICAL. */
export function playAlertSound(severity: Severity): void {
  const ctx = audioContext();
  if (!ctx) return;
  const tones = severity >= Severity.CRITICAL ? [988, 740, 988, 740] : [880];
  tones.forEach((frequency, i) => {
    const start = ctx.currentTime + i * 0.2;
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.22, start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.18);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(start);
    oscillator.stop(start + 0.2);
  });
}

function showNotification(alert: Alert): void {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  try {
    const notification = new Notification(`${SEVERITY_NAMES[alert.severity]}: ${alert.title}`, {
      body: alert.body,
      tag: alert.key,
    });
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
  } catch {
    // Some browsers only allow notifications from a service worker; the banner still shows.
  }
}

/** Renders nothing; watches the alert list and announces new HIGH/CRITICAL alerts. */
export function AlertNotifier({ alerts, sessionId }: { alerts: Alert[]; sessionId: string }) {
  const known = useRef<Set<string> | null>(null);

  useEffect(() => {
    const keyOf = (alert: Alert) => `${sessionId}|${alert.key}`;
    if (known.current === null) {
      known.current = new Set(alerts.map(keyOf)); // existing at page load: never announced
      return;
    }
    const fresh = alerts.filter((alert) => !known.current?.has(keyOf(alert)));
    if (fresh.length === 0) return;
    for (const alert of fresh) known.current.add(keyOf(alert));
    const loud = fresh.filter((alert) => alert.severity >= Severity.HIGH);
    if (loud.length === 0) return;
    playAlertSound(Math.max(...loud.map((alert) => alert.severity)) as Severity);
    for (const alert of loud.slice(0, 3)) showNotification(alert);
  }, [alerts, sessionId]);

  return null;
}
