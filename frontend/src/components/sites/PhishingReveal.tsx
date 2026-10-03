import Link from "next/link";

import { SimulatedFooter } from "./SiteFrame";

/**
 * Shown right after a password was typed on the fake page: what just happened, that
 * nothing was kept, that IT already knows, and what to do now.
 */
export function PhishingReveal({ host, mailbox }: { host: string; mailbox: string }) {
  return (
    <main data-theme="light" className="flex min-h-screen flex-col bg-bg text-ink">
      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <section
          role="alert"
          className="w-full max-w-xl animate-slide-in rounded-2xl border border-critical/30 bg-panel p-8 shadow-lg"
        >
          <p className="text-xs font-bold uppercase tracking-widest text-critical">Simulation</p>
          <h1 className="mt-2 text-2xl font-semibold">This was a simulated phishing page</h1>
          <p className="mt-3 text-muted">
            <span className="font-mono text-ink">{host}</span> only looked like a Microsoft sign-in page. It is not
            Microsoft, and it is not an approved sign-in page of your company.
          </p>

          <ul className="mt-6 space-y-3 text-[15px]">
            <li className="flex gap-3">
              <span aria-hidden className="text-low">✓</span>
              <span>
                <strong>Nothing you typed was stored or sent.</strong> This demo page never keeps a password.
              </span>
            </li>
            <li className="flex gap-3">
              <span aria-hidden className="text-critical">!</span>
              <span>In a real attack, your password would now be in the attacker&apos;s hands.</span>
            </li>
            <li className="flex gap-3">
              <span aria-hidden className="text-accent">i</span>
              <span>
                Your IT admin was alerted automatically, before you said anything (a simulated browser report that a
                work password was typed on an unapproved site).
              </span>
            </li>
          </ul>

          <h2 className="mt-8 text-sm font-semibold uppercase tracking-wider text-muted">What to do now</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-[15px]">
            <li>
              Change your password on the real company sign-in page,{" "}
              <Link href="/demo/sso.lakeside-logistics.example" className="font-mono text-accent underline">
                sso.lakeside-logistics.example
              </Link>
              , never through a link in an email.
            </li>
            <li>Sign out of your other sessions, so a stolen sign-in stops working.</li>
            <li>Check your MFA settings: no new phone or app should be listed.</li>
            <li>Tell IT what happened: in your mailbox, open the email and answer &ldquo;What happened?&rdquo;.</li>
          </ol>

          <Link
            href={mailbox}
            className="mt-8 inline-flex items-center rounded-lg bg-accent px-5 py-2.5 font-semibold text-accent-ink hover:opacity-90"
          >
            Back to my mailbox
          </Link>
        </section>
      </div>
      <SimulatedFooter />
    </main>
  );
}
