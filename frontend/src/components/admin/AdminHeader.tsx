"use client";

import { useState } from "react";

import { LIVE } from "@/lib/api";
import { Severity } from "@/lib/contracts";
import { useLiveConnection } from "@/lib/live/events";
import { ADMIN_EMPLOYEE_ID, EMPLOYEE_BY_ID, ORG } from "@/lib/mocks";
import { initials } from "@/components/ui/format";

import { playAlertSound, unlockAlertSound } from "./AlertNotifier";

type Permission = NotificationPermission | "unsupported";

export function AdminHeader() {
  const admin = EMPLOYEE_BY_ID[ADMIN_EMPLOYEE_ID];
  const connection = useLiveConnection();
  const [permission, setPermission] = useState<Permission>(() =>
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );

  async function enableAlerts() {
    unlockAlertSound();
    playAlertSound(Severity.HIGH); // a test beep, so the presenter hears that sound works
    if (typeof Notification === "undefined") return;
    setPermission(await Notification.requestPermission());
  }

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-panel/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2.5">
          <span aria-hidden className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent">
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold">Security Copilot</p>
            <p className="text-xs text-muted">{ORG.name} · Admin console</p>
          </div>
        </div>

        <ConnectionBadge connection={connection} />

        <div className="ml-auto flex items-center gap-3">
          <AlertsButton permission={permission} onEnable={enableAlerts} />
          {admin && (
            <div className="flex items-center gap-2" title={`${admin.name}, ${admin.title}`}>
              <span className="grid size-8 place-items-center rounded-full bg-panel-2 text-xs font-semibold ring-1 ring-line">
                {initials(admin.name)}
              </span>
              <div className="hidden leading-tight sm:block">
                <p className="text-sm">{admin.name}</p>
                <p className="text-xs text-muted">{admin.title}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function AlertsButton({ permission, onEnable }: { permission: Permission; onEnable: () => void }) {
  if (permission === "granted") {
    return (
      <button
        type="button"
        onClick={onEnable}
        className="rounded-md px-2.5 py-1.5 text-xs font-medium text-low ring-1 ring-inset ring-low/30 hover:bg-low/10"
        title="Browser notifications and sound are on. Click to play a test sound."
      >
        Alerts on
      </button>
    );
  }
  if (permission === "denied") {
    return (
      <span className="text-xs text-muted" title="Allow notifications for this site in the browser settings.">
        Notifications blocked in this browser
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onEnable}
      className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-accent-ink hover:opacity-90"
    >
      Enable alerts
    </button>
  );
}

const CONNECTION_BADGE = {
  demo: { label: "DEMO DATA", tone: "text-muted ring-line", dot: "bg-muted", title: "Running on simulated demo data" },
  open: { label: "LIVE", tone: "text-low ring-low/30", dot: "bg-low", title: "Connected to the live API" },
  connecting: { label: "CONNECTING", tone: "text-medium ring-medium/30", dot: "bg-medium", title: "Reconnecting to the live API. Alerts may be delayed." },
  closed: { label: "OFFLINE", tone: "text-critical ring-critical/30", dot: "bg-critical", title: "The live API is not reachable. What you see may be out of date." },
} as const;

function ConnectionBadge({ connection }: { connection: "connecting" | "open" | "closed" }) {
  const badge = CONNECTION_BADGE[LIVE ? connection : "demo"];
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${badge.tone}`}
      title={badge.title}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${badge.dot}`} />
      {badge.label}
    </span>
  );
}
