/**
 * The inbox list: newest first, unread in bold, and a small warning tag on every
 * email that Security Copilot scored as risky on arrival.
 */

import type { DeliveredEmail } from "@/lib/demo/selectors";
import { shortTime, timeAgo } from "@/components/ui/format";
import { RiskTag } from "./WarningBanner";

interface Props {
  inbox: DeliveredEmail[];
  now: number;
  selectedId: string | null;
  readIds: ReadonlySet<string>;
  onSelect: (id: string) => void;
}

export function MessageList({ inbox, now, selectedId, readIds, onSelect }: Props) {
  if (inbox.length === 0) {
    return <p className="px-4 py-10 text-center text-sm text-muted">No messages yet.</p>;
  }
  return (
    <ul role="list" className="divide-y divide-line">
      {inbox.map(({ email, deliveredAt }) => {
        const unread = !readIds.has(email.id);
        const selected = email.id === selectedId;
        const { message } = email;
        return (
          <li key={email.id} className="animate-slide-in">
            <button
              type="button"
              onClick={() => onSelect(email.id)}
              aria-current={selected ? "true" : undefined}
              className={`block w-full px-4 py-3 text-left ${
                selected ? "bg-accent/10" : "hover:bg-panel-2"
              } ${selected ? "border-l-4 border-accent pl-3" : ""}`}
            >
              <span className="flex items-center gap-2">
                {unread && (
                  <>
                    <span aria-hidden className="size-2 shrink-0 rounded-full bg-accent" />
                    <span className="sr-only">Unread.</span>
                  </>
                )}
                <span className={`min-w-0 flex-1 truncate text-sm ${unread ? "font-semibold text-ink" : "text-ink"}`}>
                  {message.sender_name || message.sender}
                </span>
                <time className="shrink-0 text-xs text-muted" dateTime={new Date(deliveredAt).toISOString()}>
                  {now - deliveredAt < 3_600_000 ? timeAgo(deliveredAt, now) : shortTime(deliveredAt)}
                </time>
              </span>
              <span className={`mt-0.5 block truncate text-sm ${unread ? "font-semibold text-ink" : "text-ink"}`}>{message.subject}</span>
              <span className="mt-1 flex items-center gap-2">
                <RiskTag assessment={email.assessment} />
                <span className="min-w-0 flex-1 truncate text-xs text-muted">{snippet(message.body_text)}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function snippet(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 140);
}
