"use client";

import { SEVERITY_NAMES, Severity } from "@/lib/contracts";
import type { Alert } from "@/lib/demo/selectors";
import { clockTime, timeAgo } from "@/components/ui/format";

/**
 * The newest alert the admin has not dismissed, pinned under the header. CRITICAL
 * pulses red; HIGH is orange. The region is announced to screen readers.
 */
export function AlertBanner({
  alerts,
  acknowledged,
  now,
  onView,
  onDismiss,
}: {
  alerts: Alert[];
  acknowledged: (alert: Alert) => boolean;
  now: number;
  onView: (alert: Alert) => void;
  onDismiss: (alert: Alert) => void;
}) {
  const open = alerts.filter((alert) => !acknowledged(alert));
  const alert = open[0];
  const critical = alert?.severity === Severity.CRITICAL;

  return (
    <div aria-live={critical ? "assertive" : "polite"} role="status" className="px-4 sm:px-6">
      {alert && (
        <div
          key={alert.key}
          className={`mt-4 flex animate-slide-in flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-3 ${
            critical ? "border-critical/50 bg-critical/12" : "border-high/40 bg-high/10"
          }`}
        >
          <span
            aria-hidden
            className={`grid size-9 shrink-0 place-items-center rounded-full ${
              critical ? "animate-pulse-ring bg-critical text-bg" : "bg-high text-bg"
            }`}
          >
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M12 8v5m0 3.5v.5" strokeLinecap="round" />
              <path d="M10.3 3.9L2.6 17.2A2 2 0 004.3 20h15.4a2 2 0 001.7-2.8L13.7 3.9a2 2 0 00-3.4 0z" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm">
              <span className={`mr-2 text-[11px] font-bold tracking-wider ${critical ? "text-critical" : "text-high"}`}>
                {critical ? "NEW CRITICAL ALERT" : `NEW ${SEVERITY_NAMES[alert.severity]} ALERT`}
              </span>
              <span className="font-semibold">{alert.title}</span>
            </p>
            <p className="mt-0.5 text-sm text-muted">
              {alert.body}{" "}
              <span className="whitespace-nowrap" title={clockTime(alert.at)}>
                · {timeAgo(alert.at, now)}
              </span>
              {open.length > 1 && <span className="whitespace-nowrap"> · {open.length - 1} more unread</span>}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onView(alert)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold text-bg hover:opacity-90 ${critical ? "bg-critical" : "bg-high"}`}
            >
              View
            </button>
            <button
              type="button"
              onClick={() => onDismiss(alert)}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-inset ring-line hover:text-ink"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
