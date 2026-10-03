"use client";

/**
 * Recommended containment (D's simulated actions). Nothing runs until the admin
 * approves it, and every result is labeled SIMULATION: no real account, mailbox
 * or infrastructure is touched.
 */

import { useState } from "react";

import { clockTime } from "@/components/ui/format";
import { SimulationBadge } from "@/components/ui/SimulationBadge";
import type { ContainmentActionType } from "@/lib/contracts";
import { ADMIN_EMPLOYEE_ID } from "@/lib/mocks";
import { containmentOptions, type ContainmentOption } from "@/lib/demo/selectors";
import { demoActions, useDemoState, useNow } from "@/lib/demo/store";

import { Heading } from "./parts";

const MAX_DETAILS = 4;

export function ContainmentSection({ campaignId, messageId }: { campaignId: string | null; messageId?: string }) {
  const state = useDemoState();
  const now = useNow();
  const options = containmentOptions(state, now, campaignId, messageId);
  const pending = options.filter((o) => o.result === null);

  // Only the actions still waiting run, so an earlier result is never overwritten
  // by a re-run against what is left (e.g. "0 messages quarantined").
  const approve = (actions: ContainmentActionType[]) =>
    demoActions.approveContainment(campaignId, actions, ADMIN_EMPLOYEE_ID, messageId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-md">
          <Heading>Recommended containment</Heading>
          <p className="text-xs leading-relaxed text-muted">
            Every action waits for your approval. All of them are simulated: nothing touches real accounts,
            mailboxes or infrastructure.
          </p>
        </div>
        {pending.length > 0 && (
          <button
            type="button"
            onClick={() => approve(pending.map((o) => o.action))}
            className="shrink-0 rounded-lg bg-critical px-4 py-2 text-sm font-semibold text-bg shadow-[0_0_24px_-8px_var(--critical)] transition hover:brightness-110"
          >
            {campaignId ? "Contain campaign" : "Approve all"}
            <span className="ml-1.5 font-normal opacity-80">({pending.length} actions)</span>
          </button>
        )}
      </div>

      <ul className="divide-y divide-line rounded-xl border border-line bg-panel-2/40">
        {options.map((option) => (
          <OptionRow key={option.action} option={option} onApprove={() => approve([option.action])} />
        ))}
      </ul>

      {pending.length === 0 && (
        <p className="flex items-center gap-2 text-sm text-low">
          <span aria-hidden>✓</span> All recommended actions approved. Track progress under Recovery.
        </p>
      )}
    </div>
  );
}

function OptionRow({ option, onApprove }: { option: ContainmentOption; onApprove: () => void }) {
  const [open, setOpen] = useState(false);
  const { result } = option;

  if (result === null) {
    return (
      <li className="flex items-center gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink">{option.label}</p>
          <p className="mt-0.5 text-xs text-muted">{option.preview}</p>
        </div>
        <button
          type="button"
          onClick={onApprove}
          className="shrink-0 rounded-lg border border-line bg-panel px-3 py-1.5 text-xs font-semibold text-ink transition hover:border-accent hover:text-accent"
        >
          Approve
        </button>
      </li>
    );
  }

  const shown = open ? result.details : result.details.slice(0, MAX_DETAILS);
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <SimulationBadge />
        <span className="text-sm font-medium text-ink">{result.summary}</span>
        <span className="ml-auto font-mono text-[11px] text-muted">{clockTime(result.at)}</span>
      </div>
      {result.details.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 pl-1 text-xs text-muted">
          {shown.map((detail, i) => (
            <li key={i} className="truncate" title={detail}>
              · {detail}
            </li>
          ))}
        </ul>
      )}
      {result.details.length > MAX_DETAILS && (
        <button type="button" onClick={() => setOpen(!open)} className="mt-1 text-xs text-accent hover:underline">
          {open ? "Show less" : `Show ${result.details.length - MAX_DETAILS} more`}
        </button>
      )}
    </li>
  );
}
