import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CompanySignIn } from "@/components/sites/CompanySignIn";
import { FakeMicrosoftSignIn } from "@/components/sites/FakeMicrosoftSignIn";
import { PlaceholderSite } from "@/components/sites/PlaceholderSite";
import { isDemoHost, siteKindFor, type SiteProps } from "@/components/sites/sites";
import { DEMO_EMPLOYEE_ID, EMPLOYEE_BY_ID, ORG } from "@/lib/mocks";

export async function generateMetadata(props: PageProps<"/demo/[host]/[[...path]]">): Promise<Metadata> {
  const host = safeDecode((await props.params).host).toLowerCase();
  const kind = isDemoHost(host) ? siteKindFor(host) : "placeholder";
  const title =
    kind === "fake-microsoft" ? "Sign in to your account"
    : kind === "company-sign-in" ? `${ORG.name} · Sign in`
    : `Simulated page · ${host}`;
  return { title, robots: { index: false, follow: false } };
}

/**
 * The simulated website behind a link in a demo email: /demo/{host}/{path}?{query}
 * stands in for https://{host}/{path}?{query}. Only reserved .example and .test
 * domains get a page. `?as=e03` shows it for another employee (default: Alice).
 */
export default async function DemoSitePage(props: PageProps<"/demo/[host]/[[...path]]">) {
  const { host: rawHost, path: segments } = await props.params;
  const query = await props.searchParams;

  const host = safeDecode(rawHost).toLowerCase().replace(/\.$/, "");
  if (!isDemoHost(host)) notFound();

  const asParam = query.as;
  const requested = Array.isArray(asParam) ? asParam[0] : asParam;
  const employee = EMPLOYEE_BY_ID[requested ?? ""] ?? EMPLOYEE_BY_ID[DEMO_EMPLOYEE_ID];

  const path = "/" + (segments ?? []).map(safeDecode).join("/");
  const search = originalSearch(query);
  const site: SiteProps = {
    host,
    path,
    search,
    pageUrl: `https://${host}${path}${search ? `?${search}` : ""}`,
    employeeId: employee.id,
    employeeEmail: employee.email,
  };

  switch (siteKindFor(host)) {
    case "fake-microsoft":
      return <FakeMicrosoftSignIn {...site} />;
    case "company-sign-in":
      return <CompanySignIn {...site} />;
    default:
      return <PlaceholderSite {...site} />;
  }
}

/** The link's own query string, without the demo's `as` parameter. */
function originalSearch(query: Record<string, string | string[] | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (key === "as" || value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, item);
  }
  return params.toString();
}

function safeDecode(text: string): string {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}
