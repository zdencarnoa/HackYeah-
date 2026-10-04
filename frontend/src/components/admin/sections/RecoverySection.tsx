"use client";

/**
 * Recovery status (D's simulated tracker): progress per area, computed from the
 * approved containment and the incident checklist, and the actions still left.
 */

import { SimulationBadge } from "@/components/ui/SimulationBadge";
import type { Incident, RecoveryTrack } from "@/lib/contracts";
import { recoveryStatus } from "@/lib/demo/selectors";
import { demoActions, useDemoState, useNow } from "@/lib/demo/store";

import { Heading, Panel } from "./parts";

export function RecoverySection({ incident }: { incident: Incident | undefined }) {
  const state = useDemoState();
  const now = useNow();

  if (!incident) {
    return (
      <p className="text-sm text-muted">
        No incident yet. Recovery tracking starts when an incident is opened, for example after a click or a
        password entry.
      </p>
    );
  }

  const status = recoveryStatus(state, now, incident);
  const allDone = status.remaining_actions.length === 0 && status.tracks.every((t) => t.percent === 100);

  return (
    <div className="space-y-5">
      <Heading right={<SimulationBadge />}>Recovery status</Heading>

      {allDone && (
        <Panel className="border-low/40 bg-low/10">
          <p className="text-sm font-medium text-low">✓ All done. The incident can be closed.</p>
          <p className="mt-0.5 text-xs text-muted">Keep an eye on the account for a few days; recovery does not prove nothing was taken.</p>
        </Panel>
      )}

      <ul className="space-y-3">
        {status.tracks.map((track) => (
          <TrackBar key={track.name} track={track} />
        ))}
      </ul>

      {status.remaining_actions.length > 0 && (
        <section>
          <Heading>Remaining actions</Heading>
          <ul className="divide-y divide-line rounded-xl border border-line bg-panel-2/40">
            {status.remaining_actions.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
                <input
                  id={`recovery-${item.id}`}
                  type="checkbox"
                  checked={item.done}
                  onChange={() => demoActions.setChecklistItem(item.id, true)}
                  className="size-4 shrink-0 accent-low"
                />
                <label htmlFor={`recovery-${item.id}`} className="cursor-pointer text-sm text-ink">
                  {item.label}
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function TrackBar({ track }: { track: RecoveryTrack }) {
  const color = track.percent === 100 ? "bg-low" : track.percent >= 50 ? "bg-accent" : track.percent > 0 ? "bg-medium" : "bg-line";
  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="text-ink">{track.name}</span>
        <span className={`font-mono text-xs tabular-nums ${track.percent === 100 ? "text-low" : "text-muted"}`}>
          {track.percent}%
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-panel"
        role="progressbar"
        aria-label={track.name}
        aria-valuenow={track.percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${color}`} style={{ width: `${track.percent}%` }} />
      </div>
    </li>
  );
}
