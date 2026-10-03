"use client";

/**
 * The admin console: one list of warning and dangerous emails across the company,
 * with everything else (incident, campaign, blast radius, containment, recovery)
 * opening from a selected email. Reads the shared demo state, so it updates the
 * moment Alice clicks or types a password in the other window.
 */

import { useState } from "react";

import type { Incident } from "@/lib/contracts";
import {
  alerts as alertsOf,
  campaignViews,
  compromisedEmployeeIds,
  deliveredEmails,
  flaggedEmails,
  incidents as incidentsOf,
  type Alert,
  type CampaignView,
  type FlaggedEmail,
} from "@/lib/demo/selectors";
import { useDemoState, useNow } from "@/lib/demo/store";

import { AdminHeader } from "./AdminHeader";
import { AlertBanner } from "./AlertBanner";
import { AlertNotifier } from "./AlertNotifier";
import { CampaignStrip } from "./CampaignStrip";
import { DemoBar } from "./DemoBar";
import { EmailDetailPanel, type DetailTab } from "./EmailDetailPanel";
import { FlaggedEmailList } from "./FlaggedEmailList";
import { OverviewTiles } from "./OverviewTiles";

type EmailKind = "campaign" | "single";

const ACK_KEY = "security-copilot-acknowledged-alerts";

function readAcknowledged(): string[] {
  try {
    return JSON.parse(window.sessionStorage.getItem(ACK_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

export function AdminConsole() {
  const state = useDemoState();
  const now = useNow(500);
  const sessionId = state.session.id;

  const flagged = flaggedEmails(state, now);
  const campaigns = campaignViews(state, now);
  const incidents = incidentsOf(state, now);
  const alerts = alertsOf(state, now);
  const compromised = compromisedEmployeeIds(state, now);
  const deliveredCount = deliveredEmails(state, now).length;

  // Selection and dismissed alerts belong to one demo session: a reset clears both.
  const [selection, setSelection] = useState<{ sessionId: string; emailId: string } | null>(null);
  const [tabByKind, setTabByKind] = useState<Record<EmailKind, DetailTab>>({ campaign: "overview", single: "overview" });
  const [acknowledged, setAcknowledged] = useState<string[]>(readAcknowledged);

  const selected = selection?.sessionId === sessionId ? flagged.find((f) => f.email.id === selection.emailId) : undefined;
  const selectedIncident = selected ? incidentFor(selected, incidents) : undefined;

  function select(email: FlaggedEmail, tab?: DetailTab) {
    setSelection({ sessionId, emailId: email.email.id });
    if (tab) setTabByKind((current) => ({ ...current, [kindOf(email)]: tab }));
  }

  function viewAlert(alert: Alert) {
    const email =
      flagged.find((f) => f.email.id === alert.messageId) ??
      earliest(flagged.filter((f) => alert.campaignId && f.campaign?.id === alert.campaignId)) ??
      flagged.find((f) => alert.employeeId && f.email.recipient_ids.includes(alert.employeeId));
    if (!email) return;
    select(email, incidentFor(email, incidents) ? "incident" : "overview");
  }

  function openCampaign(view: CampaignView) {
    const email = earliest(flagged.filter((f) => f.campaign?.id === view.campaign.id));
    if (email) select(email, "campaign");
  }

  function dismiss(alert: Alert) {
    const next = [...acknowledged, `${sessionId}|${alert.key}`];
    setAcknowledged(next);
    try {
      window.sessionStorage.setItem(ACK_KEY, JSON.stringify(next));
    } catch {
      // storage unavailable: dismissal lasts for this page view
    }
  }

  const started = state.session.startedAt !== null;

  return (
    <div className="flex min-h-screen flex-col pb-24">
      <AdminHeader />
      <AlertNotifier alerts={alerts} sessionId={sessionId} />
      <AlertBanner
        alerts={alerts}
        acknowledged={(alert) => acknowledged.includes(`${sessionId}|${alert.key}`)}
        now={now}
        onView={viewAlert}
        onDismiss={dismiss}
      />

      <div className="grid flex-1 gap-5 px-4 pt-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(26rem,0.9fr)]">
        <main className="min-w-0 space-y-5">
          <OverviewTiles flagged={flagged} campaigns={campaigns} compromised={compromised} />
          <CampaignStrip campaigns={campaigns} onOpen={openCampaign} />
          <FlaggedEmailList
            flagged={flagged}
            deliveredCount={deliveredCount}
            started={started}
            selectedId={selected?.email.id ?? null}
            now={now}
            onSelect={(email) => select(email)}
          />
        </main>

        {selected ? (
          <aside
            className="fixed inset-0 z-50 bg-bg/80 p-3 backdrop-blur-sm lg:sticky lg:inset-auto lg:top-20 lg:z-auto lg:h-[calc(100vh-10rem)] lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
            aria-label="Selected email"
          >
            <EmailDetailPanel
              key={selected.email.id}
              email={selected}
              incident={selectedIncident}
              compromised={compromised}
              tab={tabByKind[kindOf(selected)]}
              now={now}
              onTab={(tab) => setTabByKind((current) => ({ ...current, [kindOf(selected)]: tab }))}
              onClose={() => setSelection(null)}
            />
          </aside>
        ) : (
          <aside className="hidden lg:sticky lg:top-20 lg:block lg:h-[calc(100vh-10rem)]" aria-label="No email selected">
            <div className="grid h-full place-items-center rounded-xl border border-dashed border-line px-8 text-center">
              <div>
                <p className="font-semibold">Select an email</p>
                <p className="mt-1 text-sm text-muted">
                  See why it was flagged, who received it, who clicked, the campaign, the blast radius, containment and
                  recovery.
                </p>
              </div>
            </div>
          </aside>
        )}
      </div>

      <DemoBar state={state} now={now} />
    </div>
  );
}

function kindOf(email: FlaggedEmail): EmailKind {
  return email.campaign ? "campaign" : "single";
}

/** The incident this email belongs to: its campaign's, or one whose evidence names it. */
function incidentFor(email: FlaggedEmail, incidents: Incident[]): Incident | undefined {
  return incidents.find(
    (incident) =>
      (email.campaign && incident.campaign_id === email.campaign.id) ||
      incident.evidence.some((evidence) => evidence.message_id === email.email.id),
  );
}

function earliest(emails: FlaggedEmail[]): FlaggedEmail | undefined {
  return emails.reduce<FlaggedEmail | undefined>((first, f) => (!first || f.deliveredAt < first.deliveredAt ? f : first), undefined);
}
