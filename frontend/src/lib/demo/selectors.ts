/**
 * Pure views over the demo state: what each screen shows at time `now`. These
 * stand in for C's incident/campaign API and D's simulation API in mock mode and
 * return the same contract shapes, so screens do not change when the live API
 * replaces them.
 */

import {
  Severity,
  type BlastRadius,
  type BlastRadiusEdge,
  type BlastRadiusNode,
  type Campaign,
  type ContainmentActionType,
  type ContainmentResult,
  type Employee,
  type Evidence,
  type Incident,
  type RecoveryStatus,
  type TimelineItem,
} from "../contracts";
import { CAMPAIGNS, EMAILS, EMAIL_BY_ID, EMPLOYEE_BY_ID, ORG, campaignOf, type DemoEmail } from "../mocks";
import {
  ATTACK_FIRST_OFFSET_S,
  FIRST_DELIVERY_DELAY_MS,
  NO_EFFECTS,
  pastEvents,
  type ContainmentEffects,
  type DemoEvent,
  type DemoState,
  type Session,
} from "./state";

// ------------------------------------------------------------------ delivery

/** When an email lands in the inbox, or null when it has not been scheduled yet. */
export function deliveryTime(email: DemoEmail, session: Session): number | null {
  if (email.deliver_offset_s < ATTACK_FIRST_OFFSET_S) {
    // Mail from before the attack is already in the inbox at reset, minutes apart.
    return session.createdAt - (ATTACK_FIRST_OFFSET_S - email.deliver_offset_s) * 60_000;
  }
  if (session.startedAt === null) return null;
  return session.startedAt + FIRST_DELIVERY_DELAY_MS + ((email.deliver_offset_s - ATTACK_FIRST_OFFSET_S) * 1000) / session.speed;
}

export interface DeliveredEmail {
  email: DemoEmail;
  deliveredAt: number;
  /** Removed from every inbox by an approved quarantine (simulated). */
  quarantined: boolean;
  /** Arrived after its sender or domain was blocked, so it never reached an inbox. */
  blockedOnArrival: boolean;
}

/** Every email delivered by `now`, newest first. */
export function deliveredEmails(state: DemoState, now: number): DeliveredEmail[] {
  const effects = containmentEffects(state, now);
  const blocks = blockTimes(state, now);
  const out: DeliveredEmail[] = [];
  for (const email of EMAILS) {
    const deliveredAt = deliveryTime(email, state.session);
    if (deliveredAt === null || deliveredAt > now) continue;
    const domain = email.message.sender.split("@")[1] ?? "";
    const blockedAt = Math.min(blocks.get(email.message.sender) ?? Infinity, blocks.get(domain) ?? Infinity);
    out.push({
      email,
      deliveredAt,
      quarantined: effects.quarantinedMessageIds.includes(email.id),
      blockedOnArrival: deliveredAt >= blockedAt,
    });
  }
  return out.sort((a, b) => b.deliveredAt - a.deliveredAt);
}

/** The inbox of one employee: delivered to them and not removed by containment. */
export function inboxFor(state: DemoState, now: number, employeeId: string): DeliveredEmail[] {
  return deliveredEmails(state, now).filter(
    (d) => d.email.recipient_ids.includes(employeeId) && !d.quarantined && !d.blockedOnArrival,
  );
}

/** When the next scheduled email lands, for the demo bar; null when all are in. */
export function nextDeliveryAt(state: DemoState, now: number): number | null {
  const times = EMAILS.map((e) => deliveryTime(e, state.session)).filter((t): t is number => t !== null && t > now);
  return times.length ? Math.min(...times) : null;
}

// ------------------------------------------------------- what people did

export interface Interactions {
  clickedBy: string[];
  passwordBy: string[];
  reports: { employeeId: string; interaction: string; at: number }[];
}

export function interactionsFor(state: DemoState, now: number, messageId: string): Interactions {
  const events = pastEvents(state, now);
  const clickedBy = unique(events.filter((e) => e.kind === "link_clicked" && e.messageId === messageId).map(employeeOf));
  const passwordBy = unique(events.filter((e) => e.kind === "password_reuse" && e.messageId === messageId).map(employeeOf));
  const reports = events
    .filter((e): e is Extract<DemoEvent, { kind: "user_report" }> => e.kind === "user_report" && e.messageId === messageId)
    .map((e) => ({ employeeId: e.employeeId, interaction: e.interaction, at: e.at }));
  return { clickedBy, passwordBy, reports };
}

/** Did the system itself see this employee type a password on an unapproved site? */
export function passwordEntryFor(state: DemoState, now: number, employeeId: string) {
  return pastEvents(state, now).find(
    (e): e is Extract<DemoEvent, { kind: "password_reuse" }> => e.kind === "password_reuse" && e.employeeId === employeeId,
  );
}

/** Employees whose account may be compromised: a password on an unapproved site,
 * an unusual sign-in, or their own report that they entered a password. */
export function compromisedEmployeeIds(state: DemoState, now: number): string[] {
  return unique(
    pastEvents(state, now)
      .filter(
        (e) =>
          e.kind === "password_reuse" ||
          e.kind === "unusual_sign_in" ||
          (e.kind === "user_report" && (e.interaction === "password" || e.interaction === "other_info")),
      )
      .map(employeeOf),
  );
}

// ----------------------------------------------------- admin: flagged emails

export interface FlaggedEmail extends DeliveredEmail, Interactions {
  risk: Severity;
  /** Dangerous = HIGH or CRITICAL; warning = MEDIUM. */
  level: "dangerous" | "warning";
  campaign: Campaign | undefined;
  recipients: Employee[];
}

/** Every delivered email scored MEDIUM or above, most dangerous and newest first. */
export function flaggedEmails(state: DemoState, now: number): FlaggedEmail[] {
  return deliveredEmails(state, now)
    .filter((d) => d.email.assessment.risk >= Severity.MEDIUM)
    .map((d) => {
      const risk = escalatedRisk(state, now, d.email);
      return {
        ...d,
        ...interactionsFor(state, now, d.email.id),
        risk,
        level: risk >= Severity.HIGH ? ("dangerous" as const) : ("warning" as const),
        campaign: campaignOf(d.email.id),
        recipients: d.email.recipient_ids.map((id) => EMPLOYEE_BY_ID[id]).filter(Boolean),
      };
    })
    .sort((a, b) => b.risk - a.risk || b.deliveredAt - a.deliveredAt);
}

/** The scored risk, raised by what happened after delivery (C's escalation rules). */
function escalatedRisk(state: DemoState, now: number, email: DemoEmail): Severity {
  const { clickedBy, passwordBy, reports } = interactionsFor(state, now, email.id);
  if (passwordBy.length || reports.some((r) => r.interaction === "password" || r.interaction === "other_info")) {
    return Severity.CRITICAL;
  }
  if (clickedBy.length || reports.some((r) => r.interaction === "clicked" || r.interaction === "downloaded")) {
    return Math.max(email.assessment.risk, Severity.HIGH) as Severity;
  }
  return email.assessment.risk;
}

// --------------------------------------------------------------- campaigns

export interface CampaignView {
  campaign: Campaign;
  delivered: DeliveredEmail[];
  recipientsReached: Employee[];
  departmentsReached: string[];
  senderDomains: string[];
  clicks: number;
  credentialSubmissions: number;
  contained: boolean;
  firstSeenAt: number | null;
  lastSeenAt: number | null;
}

export function campaignViews(state: DemoState, now: number): CampaignView[] {
  const delivered = deliveredEmails(state, now);
  return CAMPAIGNS.map((campaign) => {
    const mine = delivered.filter((d) => campaign.message_ids.includes(d.email.id));
    const recipientIds = unique(mine.flatMap((d) => d.email.recipient_ids));
    const recipientsReached = recipientIds.map((id) => EMPLOYEE_BY_ID[id]).filter(Boolean);
    const interactions = mine.map((d) => interactionsFor(state, now, d.email.id));
    const times = mine.map((d) => d.deliveredAt);
    return {
      campaign,
      delivered: mine,
      recipientsReached,
      departmentsReached: unique(recipientsReached.map((e) => e.department)),
      senderDomains: unique(mine.map((d) => d.email.message.sender.split("@")[1] ?? "")),
      clicks: unique(interactions.flatMap((i) => i.clickedBy)).length,
      credentialSubmissions: unique(interactions.flatMap((i) => i.passwordBy)).length,
      contained: mine.length > 0 && mine.every((d) => d.quarantined || d.blockedOnArrival),
      firstSeenAt: times.length ? Math.min(...times) : null,
      lastSeenAt: times.length ? Math.max(...times) : null,
    };
  }).filter((v) => v.delivered.length > 0);
}

export function campaignView(state: DemoState, now: number, campaignId: string): CampaignView | undefined {
  return campaignViews(state, now).find((v) => v.campaign.id === campaignId);
}

// --------------------------------------------------------------- incidents

const INCIDENT_BASE_NUMBER = 1042;

interface ChecklistTemplate {
  id: string;
  action: string;
  rationale: string;
  /** Marked done automatically once a containment action covers it. */
  doneBy?: (effects: ContainmentEffects, affected: string[]) => boolean;
}

const CREDENTIAL_CHECKLIST: ChecklistTemplate[] = [
  {
    id: "revoke-sessions",
    action: "Revoke active sessions",
    rationale:
      "Because a password may have been submitted to a phishing site, ending active sessions stops an attacker from continuing to use an existing sign-in.",
    doneBy: (fx, affected) => affected.length > 0 && affected.every((id) => fx.revokedEmployeeIds.includes(id)),
  },
  {
    id: "reset-credentials",
    action: "Reset credentials",
    rationale: "A new password makes the captured one useless, even if the attacker saved it.",
    doneBy: (fx, affected) => affected.length > 0 && affected.every((id) => fx.resetEmployeeIds.includes(id)),
  },
  {
    id: "verify-mfa",
    action: "Verify MFA",
    rationale: "Attackers often add their own sign-in method to keep access. Check that no new device or method appeared.",
  },
  {
    id: "search-related",
    action: "Search for related messages",
    rationale: "Other employees may have received the same campaign. Finding the messages early prevents more exposure.",
    doneBy: (fx) => fx.quarantinedMessageIds.length > 0,
  },
  {
    id: "notify-users",
    action: "Notify affected users",
    rationale: "People who received the email should know not to open it and how to report it.",
    doneBy: (fx) => fx.notifiedEmployeeIds.length > 0,
  },
  {
    id: "review-activity",
    action: "Review account activity",
    rationale: "Look for new mailbox rules, forwarding or file downloads after the click. This does not prove misuse, but it is where misuse would show.",
  },
  {
    id: "complete-report",
    action: "Complete incident report",
    rationale: "A short written record helps with reporting duties and with preventing the next incident.",
  },
];

const GENERAL_CHECKLIST: ChecklistTemplate[] = [
  {
    id: "search-related",
    action: "Search for related messages",
    rationale: "Similar messages may have reached other employees.",
    doneBy: (fx) => fx.quarantinedMessageIds.length > 0,
  },
  {
    id: "notify-users",
    action: "Notify affected users",
    rationale: "Recipients should know what to look out for and how to report it.",
    doneBy: (fx) => fx.notifiedEmployeeIds.length > 0,
  },
  {
    id: "complete-report",
    action: "Complete incident report",
    rationale: "A short written record helps with reporting duties and learning.",
  },
];

/**
 * C's incident engine, simulated: one incident per campaign (or per single
 * message), opened by the first interaction evidence, at the severity of the
 * strongest evidence. Delivery alone is shown in the flagged list, not as an incident.
 */
export function incidents(state: DemoState, now: number): Incident[] {
  const events = pastEvents(state, now);
  const effects = containmentEffects(state, now);
  const groups = new Map<string, { campaignId: string | null; messageIds: string[]; events: DemoEvent[] }>();

  for (const event of events) {
    if (event.kind === "user_report" && event.interaction === "none") continue; // nothing to respond to
    const messageId = messageOfEvent(state, now, event);
    if (!messageId) continue;
    const campaign = campaignOf(messageId);
    const key = campaign?.id ?? messageId;
    const group = groups.get(key) ?? { campaignId: campaign?.id ?? null, messageIds: campaign?.message_ids ?? [messageId], events: [] };
    group.events.push(event);
    groups.set(key, group);
  }

  const delivered = deliveredEmails(state, now);
  return [...groups.values()].map((group, index): Incident => {
    const groupDelivered = delivered.filter((d) => group.messageIds.includes(d.email.id));
    const affected = unique(groupDelivered.flatMap((d) => d.email.recipient_ids));
    const firstEmail = groupDelivered.at(-1)?.email ?? EMAIL_BY_ID[group.messageIds[0]];
    const evidence = group.events.map((e) => toEvidence(e, messageOfEvent(state, now, e)));
    const severity = evidence.reduce<Severity>((max, e) => Math.max(max, evidenceSeverity(e)) as Severity, Severity.HIGH);
    const type = incidentType(firstEmail);
    const compromised = compromisedEmployeeIds(state, now).filter((id) => affected.includes(id));
    const template = type === "Credential phishing" ? CREDENTIAL_CHECKLIST : GENERAL_CHECKLIST;
    const id = `INC-${INCIDENT_BASE_NUMBER + index}`;
    return {
      id,
      type,
      severity,
      campaign_id: group.campaignId,
      affected_employees: affected,
      evidence,
      checklist: template.map((item) => ({
        action: item.action,
        rationale: item.rationale,
        done: checklistDone(state, now, `${id}:${item.id}`) ?? item.doneBy?.(effects, compromised) ?? false,
      })),
      timeline: timeline(groupDelivered, group.events),
      created_at: new Date(group.events[0].at).toISOString(),
    };
  });
}

/** Checklist item ids for toggling: `${incident.id}:${templateId}`, in checklist order. */
export function checklistItemIds(incident: Incident): string[] {
  const template = incident.type === "Credential phishing" ? CREDENTIAL_CHECKLIST : GENERAL_CHECKLIST;
  return template.map((item) => `${incident.id}:${item.id}`);
}

function timeline(delivered: DeliveredEmail[], events: DemoEvent[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  const first = delivered.at(-1);
  if (first) {
    const who = first.email.recipient_ids.map((id) => EMPLOYEE_BY_ID[id]?.name).filter(Boolean).join(", ");
    items.push({
      timestamp: new Date(first.deliveredAt).toISOString(),
      employee_id: first.email.recipient_ids[0],
      text: delivered.length > 1
        ? `First of ${delivered.length} related messages delivered to ${who} and scored ${riskName(first.email.assessment.risk)}`
        : `Message delivered to ${who} and scored ${riskName(first.email.assessment.risk)}`,
      source: "automatic",
    });
  }
  for (const e of events) {
    const name = EMPLOYEE_BY_ID[employeeOf(e)]?.name ?? employeeOf(e);
    const text =
      e.kind === "link_clicked" ? `${name} clicked the link to ${e.domain}`
      : e.kind === "password_reuse" ? `${name} entered a password on ${e.domain}, which is not an approved sign-in page`
      : e.kind === "unusual_sign_in" ? `Unusual sign-in to ${name}'s account from ${e.location} (${e.ip})`
      : e.kind === "user_report" ? `${name} reported: ${REPORT_TEXT[e.interaction]}`
      : null;
    if (text) {
      items.push({
        timestamp: new Date(e.at).toISOString(),
        employee_id: employeeOf(e),
        text,
        source: e.kind === "user_report" ? "reported" : "automatic",
      });
    }
  }
  return items.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

export const REPORT_TEXT: Record<string, string> = {
  none: "I haven't interacted with it",
  clicked: "I clicked the link",
  downloaded: "I downloaded an attachment",
  password: "I entered my password",
  other_info: "I entered other information",
};

function incidentType(email: DemoEmail | undefined): string {
  const categories = new Set(email?.assessment.signals.map((s) => s.category) ?? []);
  if (categories.has("credential_request") || categories.has("lookalike_domain")) return "Credential phishing";
  if (categories.has("payment_change")) return "Invoice fraud";
  if (categories.has("gift_card") || categories.has("colleague_impersonation")) return "CEO fraud";
  if (categories.has("risky_attachment")) return "Malicious attachment";
  if (categories.has("mfa_code_request")) return "MFA fraud";
  return "Suspicious email";
}

function toEvidence(e: DemoEvent, messageId: string | null): Evidence {
  const base = {
    id: e.id,
    employee_id: employeeOf(e),
    message_id: messageId,
    timestamp: new Date(e.at).toISOString(),
    interaction_kind: null,
    risk: null,
  };
  switch (e.kind) {
    case "link_clicked":
      return { ...base, kind: "link_clicked", domain: e.domain, source: "automatic" };
    case "password_reuse":
      return { ...base, kind: "password_reuse", domain: e.domain, source: "automatic" };
    case "unusual_sign_in":
      return { ...base, kind: "unusual_signin", domain: null, source: "automatic" };
    default:
      return {
        ...base,
        kind: "user_report",
        domain: null,
        source: "reported",
        interaction_kind: e.kind === "user_report" ? e.interaction : null,
      };
  }
}

function evidenceSeverity(e: Evidence): Severity {
  if (e.kind === "password_reuse" || e.kind === "unusual_signin") return Severity.CRITICAL;
  if (e.kind === "user_report" && (e.interaction_kind === "password" || e.interaction_kind === "other_info")) {
    return Severity.CRITICAL;
  }
  return Severity.HIGH;
}

/** The message an event belongs to; an unusual sign-in follows the employee's password entry. */
function messageOfEvent(state: DemoState, now: number, e: DemoEvent): string | null {
  if (e.kind === "link_clicked" || e.kind === "user_report") return e.messageId;
  if (e.kind === "password_reuse") return e.messageId;
  if (e.kind === "unusual_sign_in") return e.messageId;
  return null;
}

function checklistDone(state: DemoState, now: number, itemId: string): boolean | undefined {
  const last = pastEvents(state, now)
    .filter((e): e is Extract<DemoEvent, { kind: "checklist" }> => e.kind === "checklist" && e.itemId === itemId)
    .at(-1);
  return last?.done;
}

// ------------------------------------------------------------------ alerts

export interface Alert {
  key: string;
  severity: Severity;
  title: string;
  body: string;
  at: number;
  employeeId?: string;
  messageId?: string;
  campaignId?: string;
}

/** Admin alerts, newest first: what C's SSE stream would push. */
export function alerts(state: DemoState, now: number): Alert[] {
  const out: Alert[] = [];
  for (const view of campaignViews(state, now)) {
    const ordered = view.delivered.slice().sort((a, b) => a.deliveredAt - b.deliveredAt);
    if (ordered.length >= 2) {
      out.push({
        key: `campaign-forming:${view.campaign.id}`,
        severity: Severity.HIGH,
        title: "Possible campaign forming",
        body: `Similar messages from ${view.senderDomains.join(", ")} reached ${unique(ordered.slice(0, 2).flatMap((d) => d.email.recipient_ids)).length} employees.`,
        at: ordered[1].deliveredAt,
        campaignId: view.campaign.id,
      });
    }
  }
  for (const e of pastEvents(state, now)) {
    const name = EMPLOYEE_BY_ID[employeeOf(e)]?.name ?? "An employee";
    const messageId = messageOfEvent(state, now, e) ?? undefined;
    const base = { key: `event:${e.id}`, at: e.at, employeeId: employeeOf(e), messageId, campaignId: messageId ? campaignOf(messageId)?.id : undefined };
    if (e.kind === "link_clicked") {
      const email = EMAIL_BY_ID[e.messageId];
      if (!email || email.assessment.risk < Severity.MEDIUM) continue;
      out.push({ ...base, severity: Severity.HIGH, title: `Possible exposure: ${name}`,
        body: `Clicked a link to ${e.domain} in “${email.message.subject}”.` });
    } else if (e.kind === "password_reuse") {
      out.push({ ...base, severity: Severity.CRITICAL, title: `${name} entered a password on an unapproved site`,
        body: `${e.domain} is not an approved sign-in page. Likely account compromise.` });
    } else if (e.kind === "unusual_sign_in") {
      out.push({ ...base, severity: Severity.CRITICAL, title: `Unusual sign-in: ${name}`,
        body: `Sign-in from a new location: ${e.location} (${e.ip}).` });
    } else if (e.kind === "user_report" && e.interaction !== "none") {
      out.push({ ...base, severity: e.interaction === "password" || e.interaction === "other_info" ? Severity.CRITICAL : Severity.HIGH,
        title: `${name} reported: ${REPORT_TEXT[e.interaction]}`, body: "Reported by the employee." });
    }
  }
  return out.sort((a, b) => b.at - a.at);
}

// ------------------------------------------------------------ blast radius

/** D's blast radius, simulated: what this employee's account can reach through SSO. */
export function blastRadius(employeeId: string): BlastRadius {
  const employee = EMPLOYEE_BY_ID[employeeId];
  const services = Object.fromEntries(ORG.services.map((s) => [s.id, s]));
  const idp = ORG.services.find((s) => s.kind === "identity_provider");
  const access = new Set(employee?.access ?? []);
  const nodes: BlastRadiusNode[] = [];
  const edges: BlastRadiusEdge[] = [];
  if (!employee || !idp) {
    return { employee_id: employeeId, nodes, edges, affected_service_ids: [], explanation: "Unknown employee.", simulated: true };
  }
  nodes.push({ id: employee.id, label: employee.name, kind: "employee", sensitivity: null, at_risk: true });
  nodes.push({ id: idp.id, label: idp.name, kind: "identity_provider", sensitivity: idp.sensitivity, at_risk: true });
  edges.push({ source: employee.id, target: idp.id, relation: "signs in with" });

  const affected: string[] = [];
  for (const dep of ORG.dependencies.filter((d) => d.source === idp.id)) {
    const service = services[dep.target];
    if (!service) continue;
    const atRisk = access.has(service.id);
    if (atRisk) affected.push(service.id);
    nodes.push({ id: service.id, label: service.name, kind: "service", sensitivity: service.sensitivity, at_risk: atRisk });
    edges.push({ source: idp.id, target: service.id, relation: dep.relation });
    for (const store of ORG.dependencies.filter((d) => d.source === service.id && services[d.target]?.kind === "data")) {
      const data = services[store.target];
      nodes.push({ id: data.id, label: data.name, kind: "data", sensitivity: data.sensitivity, at_risk: atRisk });
      edges.push({ source: service.id, target: data.id, relation: store.relation });
      if (atRisk) affected.push(data.id);
    }
    if (service.kind === "email") {
      nodes.push({ id: "people", label: "Colleagues' inboxes", kind: "people", sensitivity: "medium", at_risk: atRisk });
      edges.push({ source: service.id, target: "people", relation: "can send convincing mail to" });
    }
  }
  const reachableServices = affected.filter((id) => services[id]?.kind !== "data").length;
  const reachableData = affected.length - reachableServices;
  return {
    employee_id: employeeId,
    nodes,
    edges,
    affected_service_ids: affected,
    explanation:
      `If ${employee.name}'s account is compromised, an attacker may reach ${reachableServices} services and ` +
      `${reachableData} sensitive data sets through single sign-on. This does not mean they did; ` +
      `protecting the password and active sessions comes first.`,
    simulated: true,
  };
}

// ------------------------------------------------------------- containment

export interface ContainmentOption {
  action: ContainmentActionType;
  label: string;
  /** What would happen, in plain language, before approval. */
  preview: string;
  result: ContainmentResult | null;
}

/** D's recommended containment for a campaign (or single message), with results once approved. */
export function containmentOptions(state: DemoState, now: number, campaignId: string | null, messageId?: string): ContainmentOption[] {
  const plan = containmentPlan(state, now, campaignId, messageId);
  const done = new Map<ContainmentActionType, ContainmentResult>();
  for (const e of pastEvents(state, now)) {
    if (e.kind === "containment" && e.campaignId === (campaignId ?? messageId ?? null)) {
      for (const r of e.results) done.set(r.action, r);
    }
  }
  // An approved action counts as done until new targets appear (e.g. a later wave of
  // campaign mail after a quarantine); then it is offered again.
  return plan.map((p) => ({
    action: p.action, label: p.label, preview: p.preview,
    result: p.remaining === 0 ? done.get(p.action) ?? null : null,
  }));
}

interface PlannedAction {
  action: ContainmentActionType;
  label: string;
  preview: string;
  summary: string;
  details: string[];
  effects: Partial<ContainmentEffects>;
  /** Targets this action would still change; 0 once fully applied. */
  remaining: number;
}

/** The actions and what each would still change, from what has been delivered and
 * what earlier approvals already did. */
export function containmentPlan(state: DemoState, now: number, campaignId: string | null, messageId?: string): PlannedAction[] {
  const delivered = deliveredEmails(state, now);
  const fx = containmentEffects(state, now);
  const ids = campaignId ? CAMPAIGNS.find((c) => c.id === campaignId)?.message_ids ?? [] : messageId ? [messageId] : [];
  const mine = delivered.filter((d) => ids.includes(d.email.id));
  const messages = mine.filter((d) => !d.quarantined && !d.blockedOnArrival).map((d) => d.email.id);
  const senders = unique(mine.map((d) => d.email.message.sender));
  const domains = unique(senders.map((s) => s.split("@")[1] ?? ""));
  const recipients = unique(mine.flatMap((d) => d.email.recipient_ids));
  const compromised = compromisedEmployeeIds(state, now).filter((id) => recipients.includes(id));
  const names = compromised.map((id) => EMPLOYEE_BY_ID[id]?.name ?? id);
  const pending = {
    senders: senders.filter((s) => !fx.blockedSenders.includes(s)).length,
    domains: domains.filter((d) => !fx.blockedDomains.includes(d)).length,
    notify: recipients.filter((id) => !fx.notifiedEmployeeIds.includes(id)).length,
    revoke: compromised.filter((id) => !fx.revokedEmployeeIds.includes(id)).length,
    reset: compromised.filter((id) => !fx.resetEmployeeIds.includes(id)).length,
  };
  const plan: PlannedAction[] = [
    {
      action: "quarantine_messages",
      label: `Quarantine ${plural(messages.length, "message")}`,
      preview: `Removes ${plural(messages.length, "message")} from ${plural(recipients.length, "inbox", "inboxes")}.`,
      summary: `${plural(messages.length, "message")} quarantined`,
      details: messages.map((id) => `${id}: ${EMAIL_BY_ID[id]?.message.subject ?? ""}`),
      effects: { quarantinedMessageIds: messages },
      remaining: messages.length,
    },
    {
      action: "block_sender",
      label: `Block ${plural(senders.length, "sender address", "sender addresses")}`,
      preview: `New mail from ${senders.join(", ")} is stopped on arrival.`,
      summary: `${plural(senders.length, "sender")} blocked`,
      details: senders,
      effects: { blockedSenders: senders },
      remaining: pending.senders,
    },
    {
      action: "block_domain",
      label: `Block ${domains.join(", ")}`,
      preview: `Mail and links to ${domains.join(", ")} are blocked for everyone.`,
      summary: `Domain ${domains.join(", ")} blocked`,
      details: domains,
      effects: { blockedDomains: domains },
      remaining: pending.domains,
    },
    {
      action: "notify_users",
      label: `Notify ${plural(recipients.length, "employee")}`,
      preview: "Recipients get a short warning and what to do if they clicked.",
      summary: `${plural(recipients.length, "employee")} notified`,
      details: recipients.map((id) => EMPLOYEE_BY_ID[id]?.name ?? id),
      effects: { notifiedEmployeeIds: recipients },
      remaining: pending.notify,
    },
  ];
  if (compromised.length) {
    plan.push(
      {
        action: "revoke_sessions",
        label: `Revoke sessions: ${names.join(", ")}`,
        preview: "Signs the account out everywhere, so a stolen session stops working.",
        summary: `Active sessions revoked for ${names.join(", ")}`,
        details: names,
        effects: { revokedEmployeeIds: compromised },
        remaining: pending.revoke,
      },
      {
        action: "reset_credentials",
        label: `Reset password: ${names.join(", ")}`,
        preview: "Forces a new password at next sign-in, so the captured one is useless.",
        summary: `${plural(compromised.length, "affected account")} flagged and password reset`,
        details: names,
        effects: { resetEmployeeIds: compromised },
        remaining: pending.reset,
      },
    );
  }
  plan.push({
    action: "start_investigation",
    label: "Start investigation",
    preview: "Opens the response checklist and the incident report.",
    summary: "Incident response checklist created",
    details: [],
    effects: { investigationStarted: true },
    remaining: fx.investigationStarted ? 0 : 1,
  });
  return plan;
}

// ---------------------------------------------------------------- recovery

/** D's recovery tracker, simulated: progress per area from containment and the checklist. */
export function recoveryStatus(state: DemoState, now: number, incident: Incident | undefined): RecoveryStatus {
  const effects = containmentEffects(state, now);
  const campaignId = incident?.campaign_id ?? null;
  const ids = campaignId ? CAMPAIGNS.find((c) => c.id === campaignId)?.message_ids ?? [] : [];
  const delivered = deliveredEmails(state, now).filter((d) => ids.includes(d.email.id));
  const recipients = unique(delivered.flatMap((d) => d.email.recipient_ids));
  const compromised = compromisedEmployeeIds(state, now).filter((id) => recipients.includes(id));
  const checklist = incident?.checklist ?? [];
  const done = (action: string) => checklist.find((c) => c.action === action)?.done ?? false;

  const accountSteps = compromised.length
    ? compromised.flatMap((id) => [effects.revokedEmployeeIds.includes(id), effects.resetEmployeeIds.includes(id)]).concat(done("Verify MFA"))
    : [true];
  const investigation = ["Search for related messages", "Review account activity", "Verify MFA", "Complete incident report", "Notify affected users"]
    .filter((action) => checklist.some((c) => c.action === action));
  const itemIds = checklistIdsByAction(incident);
  return {
    campaign_id: campaignId,
    incident_id: incident?.id ?? null,
    tracks: [
      { name: "Account protection", percent: percent(accountSteps.filter(Boolean).length, accountSteps.length) },
      { name: "Message containment", percent: percent(delivered.filter((d) => d.quarantined || d.blockedOnArrival).length, delivered.length) },
      { name: "Affected users notified", percent: percent(recipients.filter((id) => effects.notifiedEmployeeIds.includes(id)).length, recipients.length) },
      { name: "Investigation", percent: percent(investigation.filter(done).length, investigation.length) },
    ],
    remaining_actions: checklist
      .filter((c) => !c.done)
      .map((c) => ({ id: itemIds[c.action] ?? c.action, label: c.action, done: false })),
    simulated: true,
  };
}

function checklistIdsByAction(incident: Incident | undefined): Record<string, string> {
  if (!incident) return {};
  const ids = checklistItemIds(incident);
  return Object.fromEntries(incident.checklist.map((c, i) => [c.action, ids[i]]));
}

// ----------------------------------------------------------------- helpers

/** Everything approved containment has changed so far. */
export function containmentEffects(state: DemoState, now: number): ContainmentEffects {
  const out: ContainmentEffects = structuredClone(NO_EFFECTS);
  for (const e of pastEvents(state, now)) {
    if (e.kind !== "containment") continue;
    for (const key of Object.keys(out) as (keyof ContainmentEffects)[]) {
      if (key === "investigationStarted") out.investigationStarted ||= e.effects.investigationStarted;
      else out[key] = unique([...out[key], ...e.effects[key]]);
    }
  }
  return out;
}

function blockTimes(state: DemoState, now: number): Map<string, number> {
  const times = new Map<string, number>();
  for (const e of pastEvents(state, now)) {
    if (e.kind !== "containment") continue;
    for (const target of [...e.effects.blockedSenders, ...e.effects.blockedDomains]) {
      if (!times.has(target)) times.set(target, e.at);
    }
  }
  return times;
}

function employeeOf(e: DemoEvent): string {
  return "employeeId" in e ? e.employeeId : "";
}

export function riskName(risk: Severity): string {
  return ["LOW", "MEDIUM", "HIGH", "CRITICAL"][risk];
}

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

function percent(part: number, whole: number): number {
  return whole === 0 ? 0 : Math.round((100 * part) / whole);
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
