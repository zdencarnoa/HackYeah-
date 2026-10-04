"use client";

/**
 * The employee's mailbox (Alice by default; `?as=e03` shows another employee).
 * Mail arrives live from the shared demo state; risky mail carries its warning on
 * arrival, and quarantined mail disappears when IT contains a campaign.
 */

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { deliveredEmails, inboxFor, passwordEntryFor } from "@/lib/demo/selectors";
import { useDemoState, useNow } from "@/lib/demo/store";
import { DEMO_EMPLOYEE_ID, EMPLOYEE_BY_ID, ORG } from "@/lib/mocks";
import { SimulationBadge } from "@/components/ui/SimulationBadge";
import { initials } from "@/components/ui/format";
import { EmlUpload } from "./EmlUpload";
import { ExposureNotice } from "./ExposureNotice";
import { MessageList } from "./MessageList";
import { ReadingPane } from "./ReadingPane";
import { UserDemoBar } from "./UserDemoBar";

type View = { kind: "email"; id: string } | { kind: "upload" } | null;

export function Mailbox() {
  const requested = useSearchParams().get("as");
  const employee = (requested && EMPLOYEE_BY_ID[requested]) || EMPLOYEE_BY_ID[DEMO_EMPLOYEE_ID];
  const state = useDemoState();
  const now = useNow();
  const inbox = inboxFor(state, now, employee.id);
  const removed = deliveredEmails(state, now).filter(
    (d) => d.email.recipient_ids.includes(employee.id) && (d.quarantined || d.blockedOnArrival),
  ).length;
  const passwordEntry = passwordEntryFor(state, now, employee.id);

  const [view, setView] = useState<View>(null);
  const [readIds, setReadIds] = useState<ReadonlySet<string>>(() => new Set());
  const [checkedIds, setCheckedIds] = useState<ReadonlySet<string>>(() => new Set());
  const open = view?.kind === "email" ? inbox.find((d) => d.email.id === view.id) ?? null : null;
  const unread = inbox.filter((d) => !readIds.has(d.email.id)).length;

  function select(id: string) {
    setView({ kind: "email", id });
    setReadIds((ids) => new Set(ids).add(id));
  }

  function setChecked(id: string, show: boolean) {
    setCheckedIds((ids) => {
      const next = new Set(ids);
      if (show) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  const paneOpen = open !== null || view?.kind === "upload";

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-panel px-4 sm:px-6">
        <span aria-hidden className="flex size-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-accent-ink">
          ✉
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{ORG.name} Mail</p>
          <p className="hidden truncate text-xs text-muted sm:block">Protected by Security Copilot</p>
        </div>
        <button
          type="button"
          onClick={() => setView({ kind: "upload" })}
          className="hidden rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-panel-2 sm:block"
        >
          Check an email file
        </button>
        <div className="flex items-center gap-2">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-ink">{employee.name}</p>
            <p className="text-xs text-muted">{employee.department} · {employee.title}</p>
          </div>
          <span
            title={`Signed in as ${employee.name}`}
            className="flex size-9 items-center justify-center rounded-full bg-accent/15 text-sm font-semibold text-accent"
          >
            {initials(employee.name)}
          </span>
        </div>
      </header>

      {passwordEntry && <ExposureNotice entry={passwordEntry} employeeId={employee.id} />}

      <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(280px,360px)_1fr]">
        <aside
          aria-label="Inbox"
          className={`min-h-0 flex-col overflow-y-auto border-r border-line bg-panel ${paneOpen ? "hidden md:flex" : "flex"}`}
        >
          <div className="flex items-baseline justify-between border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">Inbox</h2>
            <span className="text-xs text-muted">{unread > 0 ? `${unread} unread` : `${inbox.length} messages`}</span>
          </div>
          {removed > 0 && (
            <p className="flex items-center gap-2 border-b border-line bg-panel-2 px-4 py-2 text-xs text-muted">
              <SimulationBadge />
              {removed === 1 ? "1 message was removed by your IT team." : `${removed} messages were removed by your IT team.`}
            </p>
          )}
          <p aria-live="polite" className="sr-only">
            {inbox.length} messages. Newest from {inbox[0]?.email.message.sender_name ?? "nobody"}: {inbox[0]?.email.message.subject ?? ""}
          </p>
          <MessageList inbox={inbox} now={now} selectedId={open?.email.id ?? null} readIds={readIds} onSelect={select} />
          <button
            type="button"
            onClick={() => setView({ kind: "upload" })}
            className="m-4 rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted hover:bg-panel-2 sm:hidden"
          >
            Check an email file (.eml)
          </button>
        </aside>

        <main className={`min-h-0 overflow-y-auto bg-bg ${paneOpen ? "block" : "hidden md:block"}`}>
          {open ? (
            <ReadingPane
              key={open.email.id}
              delivered={open}
              employeeId={employee.id}
              checked={checkedIds.has(open.email.id)}
              onCheck={(show) => setChecked(open.email.id, show)}
              onBack={() => setView(null)}
            />
          ) : view?.kind === "upload" ? (
            <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
              <button type="button" onClick={() => setView(null)} className="mb-3 text-sm font-medium text-accent md:hidden">
                ← Inbox
              </button>
              <EmlUpload />
            </div>
          ) : (
            <EmptyPane onUpload={() => setView({ kind: "upload" })} />
          )}
        </main>
      </div>
      <UserDemoBar employeeId={employee.id} />
    </div>
  );
}

function EmptyPane({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <span aria-hidden className="text-4xl text-muted">✉</span>
      <p className="text-sm text-muted">Select a message to read it.</p>
      <p className="max-w-sm text-sm text-muted">
        Risky emails are flagged automatically when they arrive. Unsure about one?{" "}
        <button type="button" onClick={onUpload} className="font-medium text-accent underline">
          Check an email file
        </button>
        .
      </p>
    </div>
  );
}
