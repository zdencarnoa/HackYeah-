"use client";

/**
 * Who received this email and what happened to each of them: delivery, clicks,
 * passwords on unapproved sites, their own reports, and the simulated containment
 * that reached them. The most at-risk person comes first.
 */

import type { ReactNode } from "react";

import { clockTime } from "@/components/ui/format";
import type { Employee } from "@/lib/contracts";
import { REPORT_TEXT, containmentEffects, type FlaggedEmail } from "@/lib/demo/selectors";
import { pastEvents } from "@/lib/demo/state";
import { useDemoState, useNow } from "@/lib/demo/store";

import { Avatar, Chip, Heading, type ChipTone } from "./parts";

interface PersonStatus {
  employee: Employee;
  clickedAt: number | null;
  passwordAt: number | null;
  signInAt: number | null;
  reports: { interaction: string; at: number }[];
  notified: boolean;
  revoked: boolean;
  reset: boolean;
  /** 3 password entered, 2 clicked, 1 reported something, 0 nothing seen. */
  rank: number;
}

export function PeopleSection({ email }: { email: FlaggedEmail }) {
  const state = useDemoState();
  const now = useNow();
  const events = pastEvents(state, now);
  const effects = containmentEffects(state, now);
  const messageId = email.email.id;

  const people: PersonStatus[] = email.recipients.map((employee) => {
    const mine = events.filter((e) => "employeeId" in e && e.employeeId === employee.id);
    const clickedAt = mine.find((e) => e.kind === "link_clicked" && e.messageId === messageId)?.at ?? null;
    const passwordAt = mine.find((e) => e.kind === "password_reuse" && e.messageId === messageId)?.at ?? null;
    const signInAt = passwordAt !== null ? mine.find((e) => e.kind === "unusual_sign_in")?.at ?? null : null;
    const reports = email.reports.filter((r) => r.employeeId === employee.id);
    const reportedCredentials = reports.some((r) => r.interaction === "password" || r.interaction === "other_info");
    return {
      employee,
      clickedAt,
      passwordAt,
      signInAt,
      reports,
      notified: effects.notifiedEmployeeIds.includes(employee.id),
      revoked: effects.revokedEmployeeIds.includes(employee.id),
      reset: effects.resetEmployeeIds.includes(employee.id),
      rank: passwordAt !== null || reportedCredentials ? 3 : clickedAt !== null ? 2 : reports.some((r) => r.interaction !== "none") ? 1 : 0,
    };
  });
  people.sort((a, b) => b.rank - a.rank || a.employee.name.localeCompare(b.employee.name));

  return (
    <div>
      <Heading right={<span className="text-xs text-muted">{people.length} recipient{people.length === 1 ? "" : "s"}</span>}>
        Recipients
      </Heading>
      <ul className="divide-y divide-line rounded-xl border border-line bg-panel-2/40">
        {people.map((person) => (
          <PersonRow key={person.employee.id} person={person} deliveredAt={email.deliveredAt} quarantined={email.quarantined} />
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted">
        We only see clicks and password entries on this network. No click recorded does not prove someone did not
        open the email on another device.
      </p>
    </div>
  );
}

const RANK_TONE: ChipTone[] = ["neutral", "medium", "high", "critical"];

function PersonRow({ person, deliveredAt, quarantined }: { person: PersonStatus; deliveredAt: number; quarantined: boolean }) {
  const { employee } = person;
  return (
    <li className="flex gap-3 px-4 py-3">
      <Avatar name={employee.name} tone={RANK_TONE[person.rank]} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-medium text-ink">{employee.name}</span>
          <span className="text-xs text-muted">
            {employee.title} · {employee.department}
          </span>
        </div>

        <ol className="mt-1.5 space-y-1 text-xs">
          <Step at={deliveredAt} tone="muted">Delivered</Step>
          {person.clickedAt !== null && <Step at={person.clickedAt} tone="high">Clicked the link (seen automatically)</Step>}
          {person.passwordAt !== null && (
            <Step at={person.passwordAt} tone="critical">Entered a password on an unapproved site (seen automatically)</Step>
          )}
          {person.signInAt !== null && <Step at={person.signInAt} tone="critical">Unusual sign-in to this account</Step>}
          {person.reports.map((report, i) => (
            <Step key={i} at={report.at} tone="medium">
              Reported: {REPORT_TEXT[report.interaction] ?? report.interaction}
            </Step>
          ))}
          {person.rank === 0 && (
            <li className="text-muted">No click or password entry recorded</li>
          )}
        </ol>

        {(person.notified || person.revoked || person.reset || quarantined) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {quarantined && <Chip tone="sim">Message quarantined</Chip>}
            {person.notified && <Chip tone="sim">Notified</Chip>}
            {person.revoked && <Chip tone="sim">Sessions revoked</Chip>}
            {person.reset && <Chip tone="sim">Password reset</Chip>}
          </div>
        )}
      </div>
    </li>
  );
}

const STEP_TONE = { muted: "bg-line", medium: "bg-medium", high: "bg-high", critical: "bg-critical" } as const;

function Step({ at, tone, children }: { at: number; tone: keyof typeof STEP_TONE; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span aria-hidden className={`size-1.5 shrink-0 rounded-full ${STEP_TONE[tone]}`} />
      <span className="w-16 shrink-0 font-mono text-[11px] text-muted">{clockTime(at)}</span>
      <span className={tone === "critical" ? "text-critical" : tone === "high" ? "text-high" : "text-ink"}>{children}</span>
    </li>
  );
}
