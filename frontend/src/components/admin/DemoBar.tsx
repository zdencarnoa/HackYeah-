"use client";

/**
 * Hidden demo controls (team plan: launch attack, switch persona, reset). A slim
 * bar fixed at the bottom; press D to show or hide it. Everything it does is
 * simulated and reaches every open window.
 */

import { useEffect, useState } from "react";

import { LIVE, liveApi } from "@/lib/api";
import type { AttackStatus } from "@/lib/contracts";
import { nextDeliveryAt } from "@/lib/demo/selectors";
import type { DemoState } from "@/lib/demo/state";
import { demoActions } from "@/lib/demo/store";
import { clearLiveAlerts } from "@/lib/live/alerts";
import { resetLiveIncidents } from "@/lib/live/incidents";
import { useLiveAttack } from "@/lib/live/attack";

const OPEN_KEY = "security-copilot-demo-bar-open";
const SPEEDS = [1, 4, 10];

function readOpen(): boolean {
  try {
    return window.sessionStorage.getItem(OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

function writeOpen(open: boolean): void {
  try {
    window.sessionStorage.setItem(OPEN_KEY, open ? "1" : "0");
  } catch {
    // storage unavailable: the bar still toggles for this page view
  }
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** `state` is the mock session; the live console passes null and the bar reads the attack engine instead. */
export function DemoBar({ state, now }: { state: DemoState | null; now: number }) {
  const [open, setOpen] = useState(readOpen);
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== "d" || event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      setOpen((current) => {
        writeOpen(!current);
        return !current;
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function toggle() {
    writeOpen(!open);
    setOpen(!open);
  }

  const live = useLiveAttack();
  const [speedChoice, setSpeedChoice] = useState(SPEEDS[1]);
  const [busy, setBusy] = useState(false);

  // Live mode shows what the attack engine reports; mock mode shows the local session.
  const started = LIVE ? Boolean(live.status && (live.status.running || live.status.delivered_count > 0)) : state?.session.startedAt != null;
  const speed = LIVE ? (live.status?.speed ?? speedChoice) : (state?.session.speed ?? speedChoice);
  const finished = LIVE && live.status !== null && live.status.delivered_count >= live.status.total_count;
  const nextInSeconds = LIVE
    ? live.status?.next_delivery_at_seconds != null
      ? Math.max(0, Math.ceil((live.status.next_delivery_at_seconds - live.status.demo_seconds_elapsed) / Math.max(speed, 0.001)))
      : null
    : (() => {
        const next = state ? nextDeliveryAt(state, now) : null;
        return next === null ? null : Math.max(0, Math.ceil((next - now) / 1000));
      })();
  const next = LIVE ? (finished ? null : nextInSeconds) : nextInSeconds;

  /** Run one live action and show its outcome, never failing silently. */
  async function act(run: () => Promise<{ ok: true; data: AttackStatus } | { ok: false; error: string }>) {
    setBusy(true);
    const result = await run();
    live.show(result.ok ? result.data : null, result.ok ? null : result.error);
    setBusy(false);
  }

  function launch() {
    if (LIVE) void act(() => liveApi.launchAttack("microsoft", speedChoice));
    else demoActions.launchAttack();
  }

  function chooseSpeed(value: number) {
    setSpeedChoice(value);
    if (!LIVE) demoActions.setSpeed(value);
    else if (live.status?.running) void act(() => liveApi.launchAttack(live.status?.scenario ?? "microsoft", value));
  }

  function skipAhead() {
    if (LIVE) void act(() => liveApi.stepAttack());
    else demoActions.fastForward(60);
  }

  async function resetEverything() {
    if (!LIVE) return demoActions.reset();
    setBusy(true);
    const result = await liveApi.reset();
    if (result.ok) {
      demoActions.reset(); // clicks and password entries kept in this browser, in every window
      clearLiveAlerts();
      resetLiveIncidents();
      live.show(null, null);
      const status = await liveApi.attackStatus();
      if (status.ok) live.show(status.data);
    } else {
      live.show(null, result.error);
    }
    setBusy(false);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={toggle}
        className="fixed right-4 bottom-4 z-40 rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-muted shadow-lg hover:text-ink"
        title="Demo controls (press D)"
      >
        Demo controls <kbd className="ml-1 rounded bg-panel-2 px-1 font-mono text-[10px] ring-1 ring-line">D</kbd>
      </button>
    );
  }

  return (
    <div role="region" aria-label="Demo controls" className="fixed inset-x-0 bottom-0 z-40 border-t border-sim/40 bg-panel/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:px-6">
        <span className="text-[11px] font-bold tracking-wider text-sim uppercase">Demo</span>

        <button
          type="button"
          onClick={launch}
          disabled={started || busy}
          className="rounded-md bg-critical px-3 py-1.5 text-xs font-semibold text-bg hover:opacity-90 disabled:cursor-not-allowed disabled:bg-panel-2 disabled:text-muted disabled:ring-1 disabled:ring-line"
        >
          {started ? "Attack launched" : "Launch attack"}
        </button>

        <div className="flex items-center rounded-md ring-1 ring-line" role="group" aria-label="Delivery speed">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={speed === s}
              onClick={() => chooseSpeed(s)}
              className={`px-2.5 py-1.5 text-xs tabular-nums first:rounded-l-md last:rounded-r-md ${
                speed === s ? "bg-accent/20 font-semibold text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {s}×
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={skipAhead}
          disabled={!started || next === null || busy}
          className="rounded-md px-2.5 py-1.5 text-xs text-ink ring-1 ring-inset ring-line hover:bg-panel-2 disabled:cursor-not-allowed disabled:text-muted"
          title={LIVE ? "Deliver the next email now" : "Skip one minute of the attack script"}
        >
          {LIVE ? "Next email" : "+1 min"}
        </button>

        <span className="text-xs text-muted tabular-nums" aria-live="polite">
          {!started
            ? "Waiting to launch"
            : next === null
              ? "All emails delivered"
              : `Next email in ${next} s`}
          {LIVE && live.status && started ? ` · ${live.status.delivered_count}/${live.status.total_count} delivered` : ""}
        </span>

        <span className="flex items-center gap-1 text-xs text-muted" role="group" aria-label="Switch persona">
          Persona:
          <span className="rounded-md bg-accent px-2 py-1 font-semibold text-accent-ink" aria-current="page">Admin</span>
          <a href="/user" className="rounded-md px-2 py-1 text-ink ring-1 ring-inset ring-line hover:bg-panel-2">
            Alice
          </a>
        </span>

        <button
          type="button"
          onClick={() => window.open("/user", "alice", "width=1200,height=900")}
          className="rounded-md px-2.5 py-1.5 text-xs text-ink ring-1 ring-inset ring-line hover:bg-panel-2"
        >
          Open Alice&apos;s mailbox in a new window ↗
        </button>

        <div className="ml-auto flex items-center gap-2">
          {confirmReset ? (
            <>
              <span className="text-xs">Reset the demo in every window?</span>
              <button
                type="button"
                onClick={() => {
                  void resetEverything();
                  setConfirmReset(false);
                }}
                className="rounded-md bg-critical px-2.5 py-1.5 text-xs font-semibold text-bg hover:opacity-90"
              >
                Yes, reset
              </button>
              <button
                type="button"
                onClick={() => setConfirmReset(false)}
                className="rounded-md px-2.5 py-1.5 text-xs text-muted ring-1 ring-inset ring-line hover:text-ink"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmReset(true)}
              className="rounded-md px-2.5 py-1.5 text-xs text-ink ring-1 ring-inset ring-line hover:bg-panel-2"
            >
              Reset demo
            </button>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label="Hide demo controls"
            className="grid size-7 place-items-center rounded-md text-muted ring-1 ring-inset ring-line hover:text-ink"
            title="Hide (press D)"
          >
            ×
          </button>
        </div>
      </div>
      {LIVE && live.error && (
        <p role="alert" className="border-t border-line px-4 py-1 text-[11px] text-critical sm:px-6">
          {live.error}
        </p>
      )}
      <p className="border-t border-line px-4 py-1 text-[11px] text-muted sm:px-6">
        All data and actions are simulated. No real accounts, mailboxes or websites are touched.
      </p>
    </div>
  );
}
