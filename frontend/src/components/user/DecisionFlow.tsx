"use client";

/**
 * "What happened?" after a check (idea.md §8). Each answer gives guidance for that
 * case; confirming sends it to IT as reported evidence. When the system already
 * saw the click or the password entry itself, it says so instead of asking blind.
 */

import Link from "next/link";
import { useState, type ReactNode } from "react";

import type { InteractionKind } from "@/lib/contracts";
import { demoPageFor } from "@/lib/api";
import { pastEvents } from "@/lib/demo/state";
import { interactionsFor, passwordEntryFor } from "@/lib/demo/selectors";
import { demoActions, useDemoState, useNow } from "@/lib/demo/store";
import { ORG } from "@/lib/mocks";
import { shortTime } from "@/components/ui/format";

const CHOICES: { kind: InteractionKind; label: string }[] = [
  { kind: "none", label: "I haven't interacted with it" },
  { kind: "clicked", label: "I clicked the link" },
  { kind: "downloaded", label: "I downloaded an attachment" },
  { kind: "password", label: "I entered my password" },
  { kind: "other_info", label: "I entered other information" },
];

/** The company's real sign-in page, for changing a password the safe way. */
function signInPage(employeeId: string): string | null {
  return demoPageFor(`https://${ORG.approved_logins[0]?.domain ?? "sso.lakeside-logistics.example"}/`, employeeId);
}

export function DecisionFlow({ employeeId, messageId }: { employeeId: string; messageId: string }) {
  const state = useDemoState();
  const now = useNow();
  const click = pastEvents(state, now).find(
    (e) => e.kind === "link_clicked" && e.employeeId === employeeId && e.messageId === messageId,
  );
  const passwordEntry = passwordEntryFor(state, now, employeeId);
  const reports = interactionsFor(state, now, messageId).reports.filter((r) => r.employeeId === employeeId);
  const [choice, setChoice] = useState<InteractionKind | null>(() =>
    passwordEntry ? "password" : click ? "clicked" : null,
  );
  const reported = choice ? reports.find((r) => r.interaction === choice) : undefined;

  return (
    <section aria-label="What happened?" className="rounded-xl border border-line bg-panel px-5 py-4 shadow-sm">
      {(passwordEntry || click) && (
        <p className="mb-3 rounded-lg bg-critical/10 px-3 py-2 text-sm font-medium text-critical">
          {passwordEntry
            ? `We noticed you entered your password on an unapproved site (${passwordEntry.domain}) at ${shortTime(passwordEntry.at)}.`
            : `We noticed you clicked this link at ${shortTime(click!.at)}.`}
        </p>
      )}

      <fieldset>
        <legend className="text-sm font-semibold text-ink">What happened?</legend>
        <div className="mt-2 grid gap-1.5">
          {CHOICES.map((c) => (
            <label
              key={c.kind}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                choice === c.kind ? "border-accent bg-accent/10" : "border-line hover:bg-panel-2"
              }`}
            >
              <input
                type="radio"
                name={`what-happened-${messageId}`}
                value={c.kind}
                checked={choice === c.kind}
                onChange={() => setChoice(c.kind)}
                className="accent-accent"
              />
              {c.label}
            </label>
          ))}
        </div>
      </fieldset>

      {choice && (
        <div className="mt-4 animate-slide-in" aria-live="polite">
          <Guidance kind={choice} employeeId={employeeId} />
          {reported ? (
            <p className="mt-3 text-sm font-medium text-low">✓ Sent to your IT team at {shortTime(reported.at)}.</p>
          ) : (
            <button
              type="button"
              onClick={() => demoActions.reportInteraction(employeeId, messageId, choice)}
              className={`mt-3 rounded-lg px-4 py-2 text-sm font-semibold ${
                choice === "password" || choice === "other_info"
                  ? "bg-critical text-white hover:opacity-90"
                  : "bg-accent text-accent-ink hover:opacity-90"
              }`}
            >
              {choice === "none" ? "Report message" : choice === "password" || choice === "other_info" ? "Start incident response" : "Report the incident"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/** The guidance for each answer, as written in idea.md §8 and §18. */
function Guidance({ kind, employeeId }: { kind: InteractionKind; employeeId: string }) {
  if (kind === "none") {
    return (
      <Box title="Recommended action">
        <p>Do not click any links or open attachments. Reporting the message helps protect your colleagues.</p>
      </Box>
    );
  }
  if (kind === "clicked" || kind === "downloaded") {
    return (
      <Box title="Potential exposure detected" tone="high">
        <ol className="list-decimal space-y-1 pl-5">
          {kind === "clicked" ? <li>Close the page.</li> : <li>Do not open the file, and delete it from your downloads.</li>}
          <li>Do not enter additional information.</li>
          <li>Report the incident.</li>
          <li>If credentials were entered, select “I entered my password.”</li>
        </ol>
      </Box>
    );
  }
  if (kind === "password") {
    const signIn = signInPage(employeeId);
    return (
      <Box title="Potential account compromise" tone="critical">
        <p className="mb-2">Take these actions immediately:</p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            Change your password using the legitimate service
            {signIn && (
              <>
                {" "}(<Link href={signIn} className="font-medium text-accent underline">company sign-in page</Link>)
              </>
            )}
            .
          </li>
          <li>Revoke active sessions if possible.</li>
          <li>Verify MFA.</li>
          <li>Notify your administrator.</li>
        </ol>
      </Box>
    );
  }
  return (
    <Box title="Potential data exposure" tone="critical">
      <ol className="list-decimal space-y-1 pl-5">
        <li>Write down what you entered and when.</li>
        <li>If it was bank or card details, call your bank now.</li>
        <li>Do not reply to the sender.</li>
        <li>Notify your administrator.</li>
      </ol>
    </Box>
  );
}

function Box({ title, tone, children }: { title: string; tone?: "high" | "critical"; children: ReactNode }) {
  const color = tone === "critical" ? "border-critical/40 bg-critical/10" : tone === "high" ? "border-high/40 bg-high/10" : "border-line bg-panel-2";
  const heading = tone === "critical" ? "text-critical" : tone === "high" ? "text-high" : "text-ink";
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm text-ink ${color}`}>
      <h3 className={`mb-1.5 text-xs font-bold uppercase tracking-wider ${heading}`}>{title}</h3>
      {children}
    </div>
  );
}
