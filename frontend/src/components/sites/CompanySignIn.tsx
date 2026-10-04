"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { DEMO_EMPLOYEE_ID, ORG } from "@/lib/mocks";

import { submitPasswordForm } from "./password";
import { PhishingReveal } from "./PhishingReveal";
import { SiteFrame } from "./SiteFrame";
import { mailboxHref, type SiteProps } from "./sites";

/** How long "Signed in" stays on screen before the mailbox comes back. */
const RETURN_DELAY_MS = 1800;

/**
 * The company's real single sign-on page (demo step 0). Typing a password here is
 * expected and safe, so nothing fires: no alert, no incident.
 */
export function CompanySignIn({ host, pageUrl, employeeId, employeeEmail }: SiteProps) {
  const router = useRouter();
  const [result, setResult] = useState<"form" | "signed-in" | "reported">("form");
  const mailbox = mailboxHref(employeeId, DEMO_EMPLOYEE_ID);

  useEffect(() => {
    if (result !== "signed-in") return;
    const timer = window.setTimeout(() => router.push(mailbox), RETURN_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [result, router, mailbox]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const outcome = submitPasswordForm(event.currentTarget, employeeId, pageUrl);
    if (outcome === "approved") setResult("signed-in");
    if (outcome === "reported") setResult("reported"); // only if this host is not actually approved
  }

  if (result === "reported") return <PhishingReveal host={host} mailbox={mailbox} />;

  return (
    <SiteFrame pageUrl={pageUrl}>
      <main className="flex flex-1 items-center justify-center bg-[linear-gradient(160deg,#e3eef0,#f3f6f7_55%)] px-4 py-16">
        <div className="w-full max-w-sm rounded-2xl bg-white p-8 text-[#15303a] shadow-[0_10px_30px_rgba(21,48,58,0.12)]">
          <div className="flex items-center gap-3">
            <LakesideMark />
            <div>
              <p className="text-[15px] font-semibold leading-tight">{ORG.name}</p>
              <p className="text-xs text-[#5b7480]">Company sign-in</p>
            </div>
          </div>

          {result === "signed-in" ? (
            <div role="status" className="mt-8 text-center">
              <p className="mx-auto flex size-12 items-center justify-center rounded-full bg-[#e2f4ec] text-2xl text-[#1e7a55]">
                ✓
              </p>
              <h1 className="mt-4 text-xl font-semibold">Signed in</h1>
              <p className="mt-2 text-sm text-[#5b7480]">This is your company&apos;s real sign-in page, so nothing was flagged.</p>
              <p className="mt-1 text-sm text-[#5b7480]">Taking you back to your mailbox…</p>
              <Link href={mailbox} className="mt-4 inline-block text-sm font-medium text-[#1f6f86] underline">
                Back now
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="mt-8 space-y-4" autoComplete="off">
              <h1 className="text-xl font-semibold">Sign in with your company account</h1>
              <div>
                <label htmlFor="company-email" className="text-sm font-medium">
                  Work email
                </label>
                <input
                  id="company-email"
                  name="email"
                  type="email"
                  required
                  defaultValue={employeeEmail}
                  className="mt-1 w-full rounded-lg border border-[#c9d6db] px-3 py-2 text-[15px] outline-none focus:border-[#1f6f86] focus:ring-2 focus:ring-[#1f6f86]/20"
                />
              </div>
              <div>
                <label htmlFor="company-password" className="text-sm font-medium">
                  Password
                </label>
                <input
                  id="company-password"
                  name="password"
                  type="password"
                  required
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-[#c9d6db] px-3 py-2 text-[15px] outline-none focus:border-[#1f6f86] focus:ring-2 focus:ring-[#1f6f86]/20"
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-lg bg-[#1f6f86] py-2.5 font-semibold text-white hover:bg-[#195c70]"
              >
                Sign in
              </button>
              <p className="text-center text-xs text-[#5b7480]">
                Single sign-on for {host.replace(/^sso\./, "")} · Problems? Contact the IT Helpdesk.
              </p>
            </form>
          )}
        </div>
      </main>
    </SiteFrame>
  );
}

function LakesideMark() {
  return (
    <svg aria-hidden viewBox="0 0 40 40" className="size-10">
      <rect width="40" height="40" rx="10" fill="#1f6f86" />
      <path d="M7 24c4-3 7-3 11 0s7 3 11 0 4-2 4-2" stroke="#ffffff" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M7 30c4-3 7-3 11 0s7 3 11 0 4-2 4-2" stroke="#9fd3df" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M13 18l7-8 7 8" stroke="#ffffff" strokeWidth="2.5" fill="none" strokeLinejoin="round" />
    </svg>
  );
}
