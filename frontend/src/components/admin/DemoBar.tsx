"use client";

/**
 * Hidden demo controls (team plan: launch attack, switch persona, reset). A slim
 * bar fixed at the bottom; press D to show or hide it. Everything it does is
 * simulated and reaches every open window.
 */

import { useEffect, useState } from "react";

import { nextDeliveryAt } from "@/lib/demo/selectors";
import type { DemoState } from "@/lib/demo/state";
import { demoActions } from "@/lib/demo/store";

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

export function DemoBar({ state, now }: { state: DemoState; now: number }) {
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

  const { startedAt, speed } = state.session;
  const started = startedAt !== null;
  const next = nextDeliveryAt(state, now);

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
          onClick={demoActions.launchAttack}
          disabled={started}
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
              onClick={() => demoActions.setSpeed(s)}
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
          onClick={() => demoActions.fastForward(60)}
          disabled={!started || next === null}
          className="rounded-md px-2.5 py-1.5 text-xs text-ink ring-1 ring-inset ring-line hover:bg-panel-2 disabled:cursor-not-allowed disabled:text-muted"
          title="Skip one minute of the attack script"
        >
          +1 min
        </button>

        <span className="text-xs text-muted tabular-nums" aria-live="polite">
          {!started
            ? "Waiting to launch"
            : next === null
              ? "All emails delivered"
              : `Next email in ${Math.max(0, Math.ceil((next - now) / 1000))} s`}
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
                  demoActions.reset();
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
      <p className="border-t border-line px-4 py-1 text-[11px] text-muted sm:px-6">
        All data and actions are simulated. No real accounts, mailboxes or websites are touched.
      </p>
    </div>
  );
}
