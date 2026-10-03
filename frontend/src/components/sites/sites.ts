/**
 * Which simulated site a demo address shows. Server-safe: the page picks the site
 * on the server, so nothing here may import the client-only demo store.
 * Only reserved .example and .test domains ever get a page.
 */

import { ORG } from "@/lib/mocks";

export type SiteKind = "fake-microsoft" | "company-sign-in" | "placeholder";

/** Reserved demo domains only; anything else is a 404. */
export function isDemoHost(host: string): boolean {
  return /^[a-z0-9.-]+$/.test(host) && (host.endsWith(".example") || host.endsWith(".test"));
}

/**
 * The attacker's page for anything imitating Microsoft; the company sign-in page
 * only on the company's approved sign-in addresses (so typing a password there never
 * fires); a labelled placeholder for every other demo address.
 */
export function siteKindFor(host: string): SiteKind {
  if (host.includes("micr0soft")) return "fake-microsoft";
  if (isCompanySignIn(host)) return "company-sign-in";
  return "placeholder";
}

/** The company's approved sign-in addresses (D's ApprovedLogins); same rule as
 * isApprovedLogin() in lib/demo/store.ts, which decides whether a password fires. */
function isCompanySignIn(host: string): boolean {
  return ORG.approved_logins.some((a) => host === a.domain || host.endsWith(`.${a.domain}`));
}

/** Everything a simulated site needs to know about where it is and who is looking. */
export interface SiteProps {
  host: string;
  /** "/verify", or "/" for the site root. */
  path: string;
  /** "session=7f3a00c9", without "?"; "" when there is none. */
  search: string;
  /** The address as the employee's browser would show it. */
  pageUrl: string;
  employeeId: string;
  employeeEmail: string;
}

/** Back to the mailbox of the same employee the demo is showing. */
export function mailboxHref(employeeId: string, defaultEmployeeId: string): string {
  return employeeId === defaultEmployeeId ? "/user" : `/user?as=${encodeURIComponent(employeeId)}`;
}
