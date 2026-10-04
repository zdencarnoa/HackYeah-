"use client";

/**
 * Demo step 5: the system itself saw the employee type a password on a site that is
 * not an approved company sign-in page, so it tells them first, before they report
 * anything. Confirming adds the employee's own report to the incident timeline.
 */

import Link from "next/link";

import { demoPageFor } from "@/lib/api";
import { interactionsFor } from "@/lib/demo/selectors";
import { demoActions, useDemoState, useNow } from "@/lib/demo/store";
import type { DemoEvent } from "@/lib/demo/state";
import { ORG } from "@/lib/mocks";
import { shortTime } from "@/components/ui/format";

type PasswordEntry = Extract<DemoEvent, { kind: "password_reuse" }>;

/** The company's real sign-in page, for changing a password the safe way. */
function signInPage(employeeId: string): string | null {
  return demoPageFor(`https://${ORG.approved_logins[0]?.domain ?? "sso.lakeside-logistics.example"}/`, employeeId);
}

export function ExposureNotice({ entry, employeeId }: { entry: PasswordEntry; employeeId: string }) {
  const state = useDemoState();
  const now = useNow();
  const signIn = signInPage(employeeId);
  const reported = entry.messageId
    ? interactionsFor(state, now, entry.messageId).reports.find(
        (r) => r.employeeId === employeeId && r.interaction === "password",
      )
    : undefined;

  return (
    <section role="alert" className="animate-slide-in border-b border-critical/40 bg-critical/10 px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 lg:flex-row lg:items-start lg:gap-6">
        <div className="flex-1">
          <p className="text-xs font-bold uppercase tracking-wider text-critical">Potential account compromise</p>
          <h2 className="mt-1 text-lg font-semibold text-ink">
            We noticed you entered your password on an unapproved site ({entry.domain}) at {shortTime(entry.at)}.
          </h2>
          <p className="mt-1 text-sm text-muted">
            These steps are guidance; your IT admin has been alerted automatically.
          </p>
        </div>
        <ol className="flex-1 list-decimal space-y-1 pl-5 text-sm text-ink">
          <li>
            Change your password using the legitimate service
            {signIn && (
              <>
                {" "}(<Link href={signIn} className="font-medium text-accent underline">company sign-in page</Link>)
              </>
            )}
            .
          </li>
          <li>Sign out of other sessions if you can.</li>
          <li>Check that your MFA settings have not changed.</li>
          <li>Do not enter anything more on that page.</li>
        </ol>
        <div className="shrink-0">
          {reported ? (
            <p className="text-sm font-medium text-low">✓ You confirmed it at {shortTime(reported.at)}.</p>
          ) : entry.messageId ? (
            <button
              type="button"
              onClick={() => demoActions.reportInteraction(employeeId, entry.messageId!, "password")}
              className="rounded-lg bg-critical px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              Yes, I entered my password
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
