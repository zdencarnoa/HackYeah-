import Link from "next/link";

import { SimulationBadge } from "@/components/ui/SimulationBadge";
import { DEMO_EMPLOYEE_ID } from "@/lib/mocks";

import { SiteFrame } from "./SiteFrame";
import { mailboxHref, type SiteProps } from "./sites";

/** Every other demo address: a clearly labelled stand-in, with no form to type into. */
export function PlaceholderSite({ host, path, pageUrl, employeeId }: SiteProps) {
  return (
    <SiteFrame pageUrl={pageUrl}>
      <main data-theme="light" className="flex flex-1 items-center justify-center bg-bg px-4 py-16 text-ink">
        <section className="w-full max-w-lg rounded-2xl border border-line bg-panel p-8 shadow-sm">
          <SimulationBadge />
          <h1 className="mt-3 text-xl font-semibold">This page stands in for a website in the demo</h1>
          <p className="mt-3 break-all font-mono text-sm text-muted">
            {host}
            {path === "/" ? "" : path}
          </p>
          <p className="mt-4 text-[15px] text-muted">
            The address is on a reserved demo domain, so no real website lives here. Nothing on this page is real, and
            there is nothing to type into.
          </p>
          <Link
            href={mailboxHref(employeeId, DEMO_EMPLOYEE_ID)}
            className="mt-6 inline-flex rounded-lg bg-accent px-4 py-2 font-semibold text-accent-ink hover:opacity-90"
          >
            Back to my mailbox
          </Link>
        </section>
      </main>
    </SiteFrame>
  );
}
