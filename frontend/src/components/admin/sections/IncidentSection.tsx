"use client";

/**
 * One incident as C's incident engine opens it: the header numbers, the evidence
 * timeline (each item tagged Automatic or Reported) and the response checklist
 * with the reason behind every step.
 */

import { clockTime, incidentTypeLabel } from "@/components/ui/format";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { LIVE, liveApi } from "@/lib/api";
import type { Incident, TimelineItem } from "@/lib/contracts";
import { checklistItemIds } from "@/lib/demo/selectors";
import { pastEvents } from "@/lib/demo/state";
import { demoActions, useDemoState, useNow } from "@/lib/demo/store";

import { Heading, Panel, Stat } from "./parts";

export function IncidentSection({ incident }: { incident: Incident }) {
  const state = useDemoState();
  const now = useNow();
  const ids = checklistItemIds(incident);
  // Items ticked by hand; the rest that are done were covered by approved containment.
  const ticked = new Set(pastEvents(state, now).flatMap((e) => (e.kind === "checklist" ? [e.itemId] : [])));

  const interacted = new Set(
    incident.evidence
      .filter((e) => e.kind !== "user_report" || e.interaction_kind !== "none")
      .map((e) => e.employee_id),
  );
  const compromised = new Set(
    incident.evidence
      .filter(
        (e) =>
          e.kind === "password_reuse" ||
          e.kind === "unusual_signin" ||
          (e.kind === "user_report" && (e.interaction_kind === "password" || e.interaction_kind === "other_info")),
      )
      .map((e) => e.employee_id),
  );
  const doneCount = incident.checklist.filter((item) => item.done).length;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">Incident {incident.id}</p>
          <h3 className="mt-0.5 text-lg font-semibold text-ink">{incidentTypeLabel(incident.type)}</h3>
          <p className="mt-0.5 text-xs text-muted">Opened {clockTime(incident.created_at)}</p>
        </div>
        <RiskBadge risk={incident.severity} size="lg" />
      </header>

      <div className="grid grid-cols-3 gap-4">
        <Stat value={incident.affected_employees.length} label="affected users" />
        <Stat value={interacted.size} label="confirmed interactions" tone={interacted.size ? "high" : "muted"} />
        <Stat value={compromised.size} label="potentially compromised accounts" tone={compromised.size ? "critical" : "muted"} />
      </div>

      <section>
        <Heading>Evidence timeline</Heading>
        <ol className="relative space-y-3 border-l border-line pl-5">
          {incident.timeline.map((item, i) => (
            <TimelineRow key={i} item={item} />
          ))}
        </ol>
      </section>

      <section>
        <Heading right={<span className="text-xs text-muted">{doneCount} of {incident.checklist.length} done</span>}>
          Recommended response
        </Heading>
        <Panel className="p-0">
          <ul className="divide-y divide-line">
            {incident.checklist.map((item, i) => {
              // Live incidents carry C's item ids; the mock template ids only fit mock incidents.
              const id = item.id ?? ids[i] ?? `${incident.id}:${i}`;
              const byContainment = item.done && !ticked.has(id);
              return (
                <li key={id} className="flex gap-3 px-4 py-3">
                  <input
                    id={id}
                    type="checkbox"
                    checked={item.done}
                    onChange={() =>
                      LIVE && item.id
                        ? !item.done && void liveApi.completeChecklistItem(item.id) // C publishes incident.updated
                        : demoActions.setChecklistItem(id, !item.done)
                    }
                    className="mt-0.5 size-4 shrink-0 accent-low"
                  />
                  <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
                    <span className={`text-sm font-medium ${item.done ? "text-muted line-through" : "text-ink"}`}>
                      {item.action}
                    </span>
                    {byContainment && <span className="ml-2 text-[11px] text-sim">done by approved containment</span>}
                    <span className="mt-0.5 block text-xs leading-relaxed text-muted">Why: {item.rationale}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </Panel>
        <p className="mt-2 text-xs text-muted">
          These steps are guidance based on the evidence above. They do not prove what an attacker did.
        </p>
      </section>
    </div>
  );
}

function TimelineRow({ item }: { item: TimelineItem }) {
  const reported = item.source === "reported";
  return (
    <li className="relative">
      <span
        aria-hidden
        className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ring-4 ring-panel ${reported ? "bg-medium" : "bg-accent"}`}
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-muted">{clockTime(item.timestamp)}</span>
        {reported ? (
          <span className="rounded-md border border-dashed border-medium/60 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-medium">
            Reported
          </span>
        ) : (
          <span className="rounded-md bg-accent/15 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-accent">
            Automatic
          </span>
        )}
      </div>
      <p className="mt-0.5 text-sm leading-snug text-ink">{item.text}</p>
    </li>
  );
}
