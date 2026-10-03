import Link from "next/link";

import { ORG } from "@/lib/mocks";

/** The start page: pick a window for the side-by-side demo. */
export default function Home() {
  return (
    <main data-theme="light" className="min-h-screen bg-bg px-4 py-14 text-ink">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs font-bold uppercase tracking-widest text-accent">{ORG.name} · demo</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Security Copilot</h1>
        <p className="mt-3 max-w-2xl text-lg text-muted">
          Catches phishing the moment it arrives, explains why in plain language, and walks a small team from the first
          click to full recovery.
        </p>

        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          <EntryCard
            href="/user"
            eyebrow="Employee"
            title="Mailbox: Alice Johnson, Finance"
            text="The inbox with automatic warnings, “Is this safe?” and clear next steps when something went wrong."
            dark={false}
          />
          <EntryCard
            href="/admin"
            eyebrow="Administrator"
            title="Admin console"
            text="Every warning and dangerous email across the company, live alerts, incidents, blast radius, containment and recovery."
            dark
          />
        </div>

        <section className="mt-12 rounded-2xl border border-line bg-panel p-7">
          <h2 className="text-lg font-semibold">How to run the demo</h2>
          <ol className="mt-4 list-decimal space-y-2.5 pl-5 text-[15px] text-muted marker:text-ink">
            <li>Open the employee mailbox and the admin console in two windows, side by side.</li>
            <li>
              In the admin console, press <Kbd>D</Kbd> to open the demo bar, choose <strong className="text-ink">Reset</strong>,
              then <strong className="text-ink">Launch attack</strong>.
            </li>
            <li>
              As Alice, open &ldquo;URGENT: Your account will be suspended&rdquo; and ask{" "}
              <strong className="text-ink">Is this safe?</strong> Then click the link anyway.
            </li>
            <li>Type any password on the fake sign-in page: the admin is alerted before Alice reports anything.</li>
            <li>
              In the admin console, open the campaign, look at the blast radius, approve{" "}
              <strong className="text-ink">Contain campaign</strong> and follow the recovery.
            </li>
          </ol>
        </section>

        <p className="mt-6 text-sm text-muted">
          Everything here is simulated: synthetic people and emails on reserved <code>.example</code> and{" "}
          <code>.test</code> domains. No real account, mailbox or website is touched, and no password is ever stored or
          sent.
        </p>
      </div>
    </main>
  );
}

function EntryCard(props: { href: string; eyebrow: string; title: string; text: string; dark: boolean }) {
  return (
    <Link
      href={props.href}
      data-theme={props.dark ? "dark" : "light"}
      className="group flex flex-col rounded-2xl border border-line bg-panel p-7 text-ink shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <span className="text-xs font-bold uppercase tracking-widest text-accent">{props.eyebrow}</span>
      <span className="mt-2 text-xl font-semibold">{props.title}</span>
      <span className="mt-2 flex-1 text-[15px] text-muted">{props.text}</span>
      <span className="mt-6 font-semibold text-accent">
        Open <span aria-hidden className="inline-block transition group-hover:translate-x-1">→</span>
      </span>
    </Link>
  );
}

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="rounded border border-line bg-panel-2 px-1.5 py-0.5 font-mono text-xs text-ink">{children}</kbd>
  );
}
