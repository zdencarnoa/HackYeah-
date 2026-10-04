import type { ReactNode } from "react";

import type { FlaggedEmail } from "@/lib/demo/selectors";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { clockTime, timeAgo } from "@/components/ui/format";

/**
 * The center of the admin console: every warning and dangerous email across the
 * company, most dangerous first. Everything else opens from a row.
 */
export function FlaggedEmailList({
  flagged,
  deliveredCount,
  started,
  selectedId,
  now,
  onSelect,
}: {
  flagged: FlaggedEmail[];
  /** All delivered mail, including LOW, for the calm empty state. */
  deliveredCount: number;
  started: boolean;
  selectedId: string | null;
  now: number;
  onSelect: (email: FlaggedEmail) => void;
}) {
  const dangerous = flagged.filter((f) => f.level === "dangerous");
  const warnings = flagged.filter((f) => f.level === "warning");

  if (flagged.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-line bg-panel px-6 py-12 text-center">
        <p className="font-semibold">No warning or dangerous emails</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted">
          {deliveredCount} {deliveredCount === 1 ? "email has" : "emails have"} arrived today and all scored LOW.
          {started
            ? " New mail is scanned the moment it arrives."
            : " Press D to open the demo controls and launch the simulated attack."}
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <EmailGroup
        title="Dangerous"
        hint="HIGH or CRITICAL: likely phishing or fraud"
        tone="text-critical"
        items={dangerous}
        selectedId={selectedId}
        now={now}
        onSelect={onSelect}
      />
      <EmailGroup
        title="Warning"
        hint="MEDIUM: could not be verified as safe"
        tone="text-medium"
        items={warnings}
        selectedId={selectedId}
        now={now}
        onSelect={onSelect}
      />
    </div>
  );
}

function EmailGroup({
  title,
  hint,
  tone,
  items,
  selectedId,
  now,
  onSelect,
}: {
  title: string;
  hint: string;
  tone: string;
  items: FlaggedEmail[];
  selectedId: string | null;
  now: number;
  onSelect: (email: FlaggedEmail) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section aria-label={`${title} emails`}>
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className={`text-sm font-semibold ${tone}`}>{title}</h2>
        <span className="rounded-full bg-panel-2 px-2 text-xs tabular-nums text-muted ring-1 ring-line">{items.length}</span>
        <span className="text-xs text-muted">{hint}</span>
      </div>
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-panel">
        {items.map((item) => (
          <li key={item.email.id} className="animate-slide-in">
            <EmailRow item={item} selected={item.email.id === selectedId} now={now} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function EmailRow({
  item,
  selected,
  now,
  onSelect,
}: {
  item: FlaggedEmail;
  selected: boolean;
  now: number;
  onSelect: (email: FlaggedEmail) => void;
}) {
  const { message } = item.email;
  const removed = item.quarantined || item.blockedOnArrival;
  const names = item.recipients.map((r) => r.name);
  const recipientsLabel = names.length === 1 ? names[0] : `${names.length} recipients`;

  return (
    <button
      type="button"
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(item)}
      className={`grid w-full gap-x-4 gap-y-1.5 px-4 py-3 text-left transition sm:grid-cols-[6.5rem_minmax(0,1fr)_auto] ${
        selected ? "bg-accent/10 shadow-[inset_3px_0_0_var(--accent)]" : "hover:bg-panel-2"
      } ${removed ? "opacity-60" : ""}`}
    >
      <div className="flex items-start pt-0.5">
        <RiskBadge risk={item.risk} />
      </div>
      <div className="min-w-0">
        <p className={`truncate text-sm font-medium ${removed ? "line-through decoration-muted" : ""}`}>{message.subject}</p>
        <p className="truncate text-xs text-muted">
          {message.sender_name ? `${message.sender_name} <${message.sender}>` : message.sender}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted" title={names.join(", ")}>
            To {recipientsLabel}
          </span>
          {item.campaign && <Chip className="text-accent ring-accent/35">{item.campaign.name}</Chip>}
          {item.clickedBy.length > 0 && <Chip className="text-high ring-high/40">Clicked by {item.clickedBy.length}</Chip>}
          {item.passwordBy.length > 0 && (
            <Chip className="bg-critical/12 font-semibold text-critical ring-critical/45">Password entered</Chip>
          )}
          {item.reports.length > 0 && <Chip className="text-ink ring-line">Reported</Chip>}
          {item.quarantined && <Chip className="text-sim ring-sim/35">Quarantined (simulation)</Chip>}
          {!item.quarantined && item.blockedOnArrival && (
            <Chip className="text-sim ring-sim/35">Blocked on arrival (simulation)</Chip>
          )}
        </div>
      </div>
      <p className="text-xs whitespace-nowrap text-muted sm:pt-0.5 sm:text-right" title={clockTime(item.deliveredAt)}>
        {timeAgo(item.deliveredAt, now)}
      </p>
    </button>
  );
}

function Chip({ children, className }: { children: ReactNode; className: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-[11px] ring-1 ring-inset ${className}`}>{children}</span>;
}
