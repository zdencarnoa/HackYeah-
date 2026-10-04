"use client";

import { useState, type KeyboardEvent } from "react";

import { SEVERITY_NAMES, Severity, type Incident } from "@/lib/contracts";
import type { FlaggedEmail } from "@/lib/demo/selectors";
import { RiskBadge, RISK_TEXT } from "@/components/ui/RiskBadge";
import { clockTime, timeAgo } from "@/components/ui/format";

import { AssessmentSection } from "./sections/AssessmentSection";
import { BlastRadiusSection } from "./sections/BlastRadiusSection";
import { CampaignSection } from "./sections/CampaignSection";
import { ContainmentSection } from "./sections/ContainmentSection";
import { IncidentSection } from "./sections/IncidentSection";
import { PeopleSection } from "./sections/PeopleSection";
import { RecoverySection } from "./sections/RecoverySection";

export type DetailTab = "overview" | "people" | "campaign" | "incident" | "blast" | "containment" | "recovery";

const TAB_LABEL: Record<DetailTab, string> = {
  overview: "Overview",
  people: "People",
  campaign: "Campaign",
  incident: "Incident",
  blast: "Blast radius",
  containment: "Containment",
  recovery: "Recovery",
};

/** Tabs that make sense for this email: Campaign and Incident only when they exist. */
export function availableTabs(email: FlaggedEmail, incident: Incident | undefined): DetailTab[] {
  return (["overview", "people", "campaign", "incident", "blast", "containment", "recovery"] as DetailTab[]).filter(
    (tab) => (tab !== "campaign" || email.campaign) && (tab !== "incident" || incident),
  );
}

/** Everything about one flagged email. Keyed by email id, so local state resets per email. */
export function EmailDetailPanel({
  email,
  incident,
  compromised,
  tab,
  now,
  onTab,
  onClose,
}: {
  email: FlaggedEmail;
  incident: Incident | undefined;
  compromised: string[];
  tab: DetailTab;
  now: number;
  onTab: (tab: DetailTab) => void;
  onClose: () => void;
}) {
  const tabs = availableTabs(email, incident);
  const active = tabs.includes(tab) ? tab : "overview";
  const { message } = email.email;

  function onTabKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(tabs.indexOf(active) + step + tabs.length) % tabs.length];
    onTab(next);
    document.getElementById(`admin-tab-${next}`)?.focus();
  }

  return (
    <section aria-label="Email details" className="flex h-full min-h-0 flex-col rounded-xl border border-line bg-panel">
      <header className="border-b border-line px-5 pt-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <RiskBadge risk={email.risk} />
              {incident && (
                <span className={`text-xs font-semibold ${RISK_TEXT[incident.severity]}`}>
                  {incident.id} · {SEVERITY_NAMES[incident.severity]} incident
                </span>
              )}
            </div>
            <h2 className="mt-2 text-lg leading-snug font-semibold">{message.subject}</h2>
            <p className="mt-0.5 truncate text-sm text-muted">
              {message.sender_name ? `${message.sender_name} <${message.sender}>` : message.sender}
            </p>
            <p className="mt-0.5 text-xs text-muted">
              Delivered {timeAgo(email.deliveredAt, now)} ({clockTime(email.deliveredAt)}) · to{" "}
              {email.recipients.length === 1 ? email.recipients[0].name : `${email.recipients.length} employees`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted ring-1 ring-inset ring-line hover:text-ink"
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div role="tablist" aria-label="Email detail sections" onKeyDown={onTabKey} className="-mb-px mt-4 flex flex-wrap gap-x-1">
          {tabs.map((id) => (
            <button
              key={id}
              id={`admin-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={id === active}
              aria-controls={`admin-panel-${id}`}
              tabIndex={id === active ? 0 : -1}
              onClick={() => onTab(id)}
              className={`shrink-0 border-b-2 px-3 py-2 text-sm whitespace-nowrap transition ${
                id === active ? "border-accent font-semibold text-ink" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {TAB_LABEL[id]}
              {id === "incident" && incident && (
                <span aria-hidden className={`ml-1.5 inline-block size-1.5 rounded-full align-middle ${incident.severity >= Severity.CRITICAL ? "bg-critical" : "bg-high"}`} />
              )}
            </button>
          ))}
        </div>
      </header>

      <div
        id={`admin-panel-${active}`}
        role="tabpanel"
        aria-labelledby={`admin-tab-${active}`}
        className="min-h-0 flex-1 overflow-y-auto px-5 py-4"
      >
        {active === "overview" && <AssessmentSection email={email} />}
        {active === "people" && <PeopleSection email={email} />}
        {active === "campaign" && email.campaign && <CampaignSection campaignId={email.campaign.id} />}
        {active === "incident" && incident && <IncidentSection incident={incident} />}
        {active === "blast" && <BlastRadiusTab email={email} compromised={compromised} />}
        {active === "containment" && (
          <ContainmentSection
            campaignId={email.campaign?.id ?? null}
            messageId={email.campaign ? undefined : email.email.id}
          />
        )}
        {active === "recovery" && <RecoverySection incident={incident} />}
      </div>
    </section>
  );
}

/** Blast radius for one recipient: a compromised one by default. */
function BlastRadiusTab({ email, compromised }: { email: FlaggedEmail; compromised: string[] }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const atRisk = email.recipients.find((r) => compromised.includes(r.id));
  const employeeId = chosen ?? atRisk?.id ?? email.recipients[0]?.id;
  if (!employeeId) return <p className="text-sm text-muted">This email has no known recipients.</p>;

  return (
    <div className="space-y-4">
      {email.recipients.length > 1 && (
        <label className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Show what this account can reach:</span>
          <select
            value={employeeId}
            onChange={(event) => setChosen(event.target.value)}
            className="rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-ink"
          >
            {email.recipients.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
                {compromised.includes(r.id) ? " (account at risk)" : ""}
              </option>
            ))}
          </select>
        </label>
      )}
      <BlastRadiusSection key={employeeId} employeeId={employeeId} />
    </div>
  );
}
