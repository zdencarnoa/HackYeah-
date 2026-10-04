"use client";

/**
 * The admin console in live mode: incidents and campaigns from C's API, kept
 * current by the event stream. The backend has no list of every scored message, so
 * this view is organized around incidents (what needs attention) and opens the same
 * campaign, blast radius, containment and recovery views from one.
 */

import { useState, type KeyboardEvent } from "react";

import { RISK_TEXT, RiskBadge } from "@/components/ui/RiskBadge";
import { timeAgo } from "@/components/ui/format";
import { SEVERITY_NAMES, Severity, type Campaign, type ContainmentResult, type Incident } from "@/lib/contracts";
import type { Alert } from "@/lib/demo/selectors";
import { useNow } from "@/lib/demo/store";
import { useLiveAlerts } from "@/lib/live/alerts";
import { sortIncidents, useLiveIncidents } from "@/lib/live/incidents";
import { EMPLOYEE_BY_ID } from "@/lib/mocks";

import { AdminHeader } from "../AdminHeader";
import { AlertBanner } from "../AlertBanner";
import { AlertNotifier } from "../AlertNotifier";
import { DemoBar } from "../DemoBar";
import { IncidentSection } from "../sections/IncidentSection";
import { Heading, Panel, Stat } from "../sections/parts";
import { LiveBlastRadius, LiveCampaign, LiveContainment, LiveRecovery, compromisedIn } from "./LiveSections";

type Tab = "incident" | "campaign" | "blast" | "containment" | "recovery";
const TAB_LABEL: Record<Tab, string> = {
  incident: "Incident", campaign: "Campaign", blast: "Blast radius", containment: "Containment", recovery: "Recovery",
};

const name = (id: string) => EMPLOYEE_BY_ID[id]?.name ?? id;
const TYPE_LABEL: Record<string, string> = { credential_phishing: "Credential phishing" };
const typeLabel = (type: string) => TYPE_LABEL[type] ?? type.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function LiveAdminConsole() {
  const now = useNow(1000);
  const { incidents, campaigns, loaded, error } = useLiveIncidents();
  const alerts = useLiveAlerts();
  const sorted = sortIncidents(incidents);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("incident");
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [containment, setContainment] = useState<Record<string, ContainmentResult[]>>({});
  const [recoveryVersion, setRecoveryVersion] = useState(0);

  const selected = sorted.find((i) => i.id === selectedId);
  const campaignOf = (i: Incident) => campaigns.find((c) => c.id === i.campaign_id);

  function open(incident: Incident, next: Tab = "incident") {
    setSelectedId(incident.id);
    setTab(next);
  }

  function viewAlert(alert: Alert) {
    const incident = sorted.find((i) => alert.key.startsWith(`incident:${i.id}:`));
    if (incident) open(incident);
  }

  const atRisk = new Set(sorted.flatMap(compromisedIn));
  const reached = new Set(sorted.flatMap((i) => i.affected_employees));

  return (
    <div className="flex min-h-screen flex-col pb-24">
      <AdminHeader />
      <AlertNotifier alerts={alerts} sessionId="live" />
      <AlertBanner
        alerts={alerts}
        acknowledged={(alert) => acknowledged.includes(alert.key)}
        now={now}
        onView={viewAlert}
        onDismiss={(alert) => setAcknowledged((current) => [...current, alert.key])}
      />

      <div className="grid flex-1 gap-5 px-4 pt-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(26rem,0.9fr)]">
        <main className="min-w-0 space-y-5">
          <Panel className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat value={sorted.length} label="Open incidents" tone={sorted.length ? "high" : "ink"} />
            <Stat value={sorted.filter((i) => i.severity >= Severity.CRITICAL).length} label="Critical" tone="critical" />
            <Stat value={atRisk.size} label="Accounts at risk" tone={atRisk.size ? "critical" : "ink"} />
            <Stat value={campaigns.length} label={campaigns.length === 1 ? "Campaign" : "Campaigns"} tone={campaigns.length ? "high" : "ink"} />
          </Panel>
          {reached.size > 0 && <p className="-mt-2 text-xs text-muted">{reached.size} {reached.size === 1 ? "employee" : "employees"} involved so far.</p>}

          <section aria-label="Incidents">
            <Heading>Incidents</Heading>
            {error && (
              <Panel className="mb-3 border-medium/40 bg-medium/10">
                <p className="text-sm font-medium text-medium">Live incidents could not be loaded.</p>
                <p className="mt-0.5 text-xs text-muted">{error} New incidents will still appear here when they arrive.</p>
              </Panel>
            )}
            {!loaded && <p className="text-sm text-muted">Loading incidents…</p>}
            {loaded && sorted.length === 0 && !error && (
              <div className="grid place-items-center rounded-xl border border-dashed border-line px-8 py-12 text-center">
                <div>
                  <p className="font-semibold">No incidents yet</p>
                  <p className="mt-1 text-sm text-muted">Everything delivered so far looks fine. Press D to open the demo controls and launch the simulated attack.</p>
                </div>
              </div>
            )}
            <ul className="space-y-2">
              {sorted.map((incident) => (
                <IncidentRow key={incident.id} incident={incident} campaign={campaignOf(incident)} selected={incident.id === selectedId} now={now} onOpen={() => open(incident)} />
              ))}
            </ul>
          </section>
        </main>

        {selected ? (
          <aside className="fixed inset-0 z-50 bg-bg/80 p-3 backdrop-blur-sm lg:sticky lg:inset-auto lg:top-20 lg:z-auto lg:h-[calc(100vh-10rem)] lg:bg-transparent lg:p-0 lg:backdrop-blur-none" aria-label="Selected incident">
            <IncidentPanel
              key={selected.id}
              incident={selected}
              campaign={campaignOf(selected)}
              tab={tab}
              onTab={setTab}
              onClose={() => setSelectedId(null)}
              results={containment[selected.id]}
              onResults={(results) => {
                setContainment((current) => ({ ...current, [selected.id]: results }));
                setRecoveryVersion((v) => v + 1);
              }}
              recoveryVersion={recoveryVersion}
            />
          </aside>
        ) : (
          <aside className="hidden lg:sticky lg:top-20 lg:block lg:h-[calc(100vh-10rem)]" aria-label="No incident selected">
            <div className="grid h-full place-items-center rounded-xl border border-dashed border-line px-8 text-center">
              <div>
                <p className="font-semibold">Select an incident</p>
                <p className="mt-1 text-sm text-muted">See the evidence, the campaign, the blast radius, containment and recovery.</p>
              </div>
            </div>
          </aside>
        )}
      </div>

      <DemoBar state={null} now={now} />
    </div>
  );
}

function IncidentRow({ incident, campaign, selected, now, onOpen }: { incident: Incident; campaign: Campaign | undefined; selected: boolean; now: number; onOpen: () => void }) {
  const latest = incident.timeline[incident.timeline.length - 1];
  const people = incident.affected_employees.map(name);
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        aria-current={selected}
        className={`w-full rounded-xl border px-4 py-3 text-left transition ${selected ? "border-accent bg-panel-2" : "border-line bg-panel hover:bg-panel-2"}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <RiskBadge risk={incident.severity} />
          <span className="text-sm font-semibold">{typeLabel(incident.type)}</span>
          {campaign && <span className="text-xs text-muted">· {campaign.message_ids.length} messages, {campaign.recipients.length} recipients</span>}
          <span className="ml-auto text-xs text-muted">{timeAgo(Date.parse(incident.created_at), now)}</span>
        </div>
        <p className="mt-1 truncate text-sm">{people.join(", ") || "No employee yet"}</p>
        {latest && <p className="mt-0.5 truncate text-xs text-muted">{latest.text}</p>}
      </button>
    </li>
  );
}

function IncidentPanel({
  incident, campaign, tab, onTab, onClose, results, onResults, recoveryVersion,
}: {
  incident: Incident; campaign: Campaign | undefined; tab: Tab; onTab: (tab: Tab) => void; onClose: () => void;
  results: ContainmentResult[] | undefined; onResults: (results: ContainmentResult[]) => void; recoveryVersion: number;
}) {
  const tabs = (["incident", "campaign", "blast", "containment", "recovery"] as Tab[]).filter((t) => t !== "campaign" || campaign);
  const active = tabs.includes(tab) ? tab : "incident";

  function onTabKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = tabs[(tabs.indexOf(active) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    onTab(next);
    document.getElementById(`live-tab-${next}`)?.focus();
  }

  return (
    <section aria-label="Incident details" className="flex h-full min-h-0 flex-col rounded-xl border border-line bg-panel">
      <header className="border-b border-line px-5 pt-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <RiskBadge risk={incident.severity} />
              <span className={`text-xs font-semibold ${RISK_TEXT[incident.severity]}`}>{incident.id} · {SEVERITY_NAMES[incident.severity]} incident</span>
            </div>
            <h2 className="mt-2 text-lg leading-snug font-semibold">{typeLabel(incident.type)}</h2>
            <p className="mt-0.5 truncate text-sm text-muted">{incident.affected_employees.map(name).join(", ")}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close details" className="grid size-8 shrink-0 place-items-center rounded-md text-muted ring-1 ring-inset ring-line hover:text-ink">
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" /></svg>
          </button>
        </div>
        <div role="tablist" aria-label="Incident sections" onKeyDown={onTabKey} className="-mb-px mt-4 flex flex-wrap gap-x-1">
          {tabs.map((id) => (
            <button
              key={id} id={`live-tab-${id}`} type="button" role="tab" aria-selected={id === active} aria-controls={`live-panel-${id}`}
              tabIndex={id === active ? 0 : -1} onClick={() => onTab(id)}
              className={`shrink-0 border-b-2 px-3 py-2 text-sm whitespace-nowrap transition ${id === active ? "border-accent font-semibold text-ink" : "border-transparent text-muted hover:text-ink"}`}
            >
              {TAB_LABEL[id]}
            </button>
          ))}
        </div>
      </header>
      <div id={`live-panel-${active}`} role="tabpanel" aria-labelledby={`live-tab-${active}`} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {active === "incident" && <IncidentSection incident={incident} />}
        {active === "campaign" && campaign && <LiveCampaign campaign={campaign} />}
        {active === "blast" && <LiveBlastRadius incident={incident} />}
        {active === "containment" && <LiveContainment incident={incident} campaign={campaign} results={results} onResults={onResults} />}
        {active === "recovery" && <LiveRecovery refreshKey={recoveryVersion} />}
      </div>
    </section>
  );
}
