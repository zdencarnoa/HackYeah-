"use client";

/**
 * One campaign as C's correlation sees it: how far it has spread (live counts),
 * what its messages have in common, and who it reached.
 */

import { clockTime } from "@/components/ui/format";
import { EMPLOYEE_BY_ID } from "@/lib/mocks";
import { campaignView } from "@/lib/demo/selectors";
import { useDemoState, useNow } from "@/lib/demo/store";

import { Chip, Heading, Panel, Stat } from "./parts";

export function CampaignSection({ campaignId }: { campaignId: string }) {
  const state = useDemoState();
  const now = useNow();
  const view = campaignView(state, now, campaignId);

  if (!view) {
    return <p className="text-sm text-muted">No message from this campaign has been delivered yet.</p>;
  }

  const { campaign } = view;
  const messages = view.delivered.slice().sort((a, b) => a.deliveredAt - b.deliveredAt);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">Campaign</p>
          <h3 className="mt-0.5 text-lg font-semibold text-ink">{campaign.name}</h3>
          <p className="mt-0.5 text-xs text-muted">
            {view.firstSeenAt !== null && `First seen ${clockTime(view.firstSeenAt)}`}
            {view.lastSeenAt !== null && view.lastSeenAt !== view.firstSeenAt && ` · latest ${clockTime(view.lastSeenAt)}`}
          </p>
        </div>
        {view.contained ? <Chip tone="low">Contained</Chip> : <Chip tone="critical">Active</Chip>}
      </header>

      <p className="text-2xl font-semibold tabular-nums text-ink">
        {plural(view.delivered.length, "message")} <span className="text-muted">·</span>{" "}
        {plural(view.recipientsReached.length, "recipient")} <span className="text-muted">·</span>{" "}
        {plural(view.departmentsReached.length, "department")}
      </p>

      <div className="grid grid-cols-3 gap-4">
        <Stat value={view.clicks} label="employees clicked" tone={view.clicks ? "high" : "muted"} />
        <Stat
          value={view.credentialSubmissions}
          label="passwords entered on the fake page"
          tone={view.credentialSubmissions ? "critical" : "muted"}
        />
        <Stat
          value={view.delivered.filter((d) => d.quarantined || d.blockedOnArrival).length}
          label="messages contained"
          tone={view.contained ? "low" : "muted"}
        />
      </div>

      <Panel>
        <Heading>What these messages have in common</Heading>
        <ul className="space-y-1.5">
          {campaign.shared_traits.map((trait, i) => (
            <li key={i} className="flex gap-2 text-sm text-ink">
              <span aria-hidden className="text-accent">•</span>
              {trait}
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-muted">
          Sender domain{view.senderDomains.length === 1 ? "" : "s"}:
          {view.senderDomains.map((domain) => (
            <span key={domain} className="rounded bg-panel px-1.5 py-0.5 font-mono text-[11px] text-critical">
              {domain}
            </span>
          ))}
        </div>
      </Panel>

      <section>
        <Heading>Departments reached</Heading>
        <div className="flex flex-wrap gap-1.5">
          {view.departmentsReached.map((department) => (
            <Chip key={department} tone="accent">
              {department}
            </Chip>
          ))}
        </div>
      </section>

      <section>
        <Heading>Recipients reached</Heading>
        <ul className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          {view.recipientsReached.map((employee) => (
            <li key={employee.id} className="flex items-baseline justify-between gap-2">
              <span className="truncate text-ink">{employee.name}</span>
              <span className="shrink-0 text-xs text-muted">{employee.department}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <Heading right={<span className="text-xs text-muted">oldest first</span>}>Messages</Heading>
        <ul className="divide-y divide-line rounded-xl border border-line">
          {messages.map((d) => (
            <li key={d.email.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="w-16 shrink-0 font-mono text-[11px] text-muted">{clockTime(d.deliveredAt)}</span>
              <span className="min-w-0 flex-1 truncate text-ink" title={d.email.message.subject}>
                {d.email.message.subject}
              </span>
              <span className="hidden shrink-0 truncate text-xs text-muted sm:block">
                {d.email.recipient_ids.map((id) => EMPLOYEE_BY_ID[id]?.name ?? id).join(", ")}
              </span>
              {d.quarantined && <Chip tone="sim">Quarantined</Chip>}
              {!d.quarantined && d.blockedOnArrival && <Chip tone="sim">Blocked on arrival</Chip>}
            </li>
          ))}
        </ul>
        {view.delivered.length < campaign.message_ids.length && (
          <p className="mt-2 text-xs text-muted">
            The campaign may still be growing: correlation updates as new messages arrive.
          </p>
        )}
      </section>
    </div>
  );
}

function plural(n: number, one: string): string {
  return `${n} ${n === 1 ? one : `${one}s`}`;
}
