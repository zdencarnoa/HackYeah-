/**
 * TypeScript mirror of the shared contracts.
 *
 * Source of truth: backend/app/schemas.py (detection, scoring, incidents and
 * simulation sections, all merged there). Keep field names identical; change these
 * only when the Python contracts change.
 */

// ---------------------------------------------------------------- A: detection

export interface Link {
  url: string;
  anchor_text: string | null;
  found_in: "text" | "html";
}

export interface MessageAttachment {
  filename: string;
  content_type: string;
  size_bytes: number;
  encrypted: boolean;
}

export interface Message {
  id: string;
  sender: string;
  sender_name: string;
  reply_to: string | null;
  recipients: string[];
  subject: string;
  body_text: string;
  body_html: string | null;
  urls: Link[];
  attachments: MessageAttachment[];
  headers: [string, string][];
  received_at: string;
}

export type SignalCategory =
  | "auth_failure"
  | "reply_to_mismatch"
  | "return_path_mismatch"
  | "brand_impersonation"
  | "freemail_impersonation"
  | "colleague_impersonation"
  | "lookalike_domain"
  | "suspicious_url"
  | "urgency"
  | "credential_request"
  | "payment_change"
  | "gift_card"
  | "mfa_code_request"
  | "risky_attachment"
  | "known_bad"
  | "ml_phishing";

export interface Signal {
  id: string;
  category: SignalCategory;
  /** 0 context only, 1 weak, 2 moderate, 3 strong. Not the same scale as risk. */
  severity: 0 | 1 | 2 | 3;
  evidence: string;
  technical_detail: string;
  source: "rule" | "url" | "ml" | "intel";
}

// ---------------------------------------------------------- B: risk verdict

/** B's and C's shared risk scale (IntEnum on the backend). */
export const Severity = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 } as const;
export type Severity = (typeof Severity)[keyof typeof Severity];
export const SEVERITY_NAMES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;

export interface Explanation {
  summary: string;
  reasons: string[];
  source: "llm" | "template";
}

export interface Assessment {
  message_id: string;
  risk: Severity;
  score: number;
  signals: Signal[];
  ml_confidence: number | null;
  ml_model: string | null;
  uncertainties: string[];
  explanation: Explanation;
  recommended_action: string;
  assessed_at: string;
}

// ------------------------------------------------------------- D: simulation

export type Department = "Finance" | "Sales" | "Operations" | "HR" | "IT" | "Executive";

export interface Employee {
  id: string;
  name: string;
  email: string;
  department: Department;
  title: string;
  manager_id: string | null;
  is_admin: boolean;
  access: string[];
}

export type ServiceKind = "identity_provider" | "email" | "file_storage" | "internal_app" | "data";
export type Sensitivity = "low" | "medium" | "high";

export interface Service {
  id: string;
  name: string;
  kind: ServiceKind;
  sensitivity: Sensitivity;
  description: string;
}

export interface Dependency {
  source: string;
  target: string;
  relation: string;
}

export interface ApprovedLogin {
  domain: string;
  service_id: string;
  description: string;
}

export interface Organization {
  name: string;
  domain: string;
  employees: Employee[];
  services: Service[];
  dependencies: Dependency[];
  approved_logins: ApprovedLogin[];
}

export type SimEventType =
  | "email_delivered"
  | "link_clicked"
  | "password_reuse"
  | "unusual_sign_in"
  | "containment_action"
  | "demo_reset";

export interface SimEvent {
  id: string;
  type: SimEventType;
  at: string;
  employee_id: string | null;
  message_id: string | null;
  data: Record<string, string | number | boolean>;
  simulated: true;
}

export type BlastNodeKind = "employee" | "identity_provider" | "service" | "data" | "people";

export interface BlastRadiusNode {
  id: string;
  label: string;
  kind: BlastNodeKind;
  sensitivity: Sensitivity | null;
  at_risk: boolean;
  /** Why it is (or is not) reachable, in plain language. Optional: mock data omits it. */
  reason?: string;
}

export interface BlastRadiusEdge {
  source: string;
  target: string;
  relation: string;
}

export interface BlastRadius {
  employee_id: string;
  nodes: BlastRadiusNode[];
  edges: BlastRadiusEdge[];
  affected_service_ids: string[];
  explanation: string;
  simulated: true;
}

export type ContainmentActionType =
  | "quarantine_messages"
  | "block_sender"
  | "block_domain"
  | "notify_users"
  | "disable_account"
  | "reset_credentials"
  | "revoke_sessions"
  | "start_investigation"
  | "contain_campaign";

export interface ContainmentResult {
  action: ContainmentActionType;
  /** Admin employee id. Optional: the mock store records it on the event instead. */
  approved_by?: string;
  summary: string;
  affected_count: number;
  details: string[];
  at: string;
  simulated: true;
}

export interface RecoveryTrack {
  name: string;
  percent: number;
}

export interface RecoveryChecklistItem {
  id: string;
  label: string;
  done: boolean;
}

export interface RecoveryStatus {
  campaign_id: string | null;
  incident_id: string | null;
  tracks: RecoveryTrack[];
  remaining_actions: RecoveryChecklistItem[];
  simulated: true;
}

// --------------------------------------------------- C: incidents, campaigns

export type EvidenceKind = "email_scored" | "link_clicked" | "password_reuse" | "unusual_signin" | "user_report";
export type InteractionKind = "none" | "clicked" | "downloaded" | "password" | "other_info";

export interface Evidence {
  id: string;
  kind: EvidenceKind;
  employee_id: string;
  message_id: string | null;
  domain: string | null;
  source: "automatic" | "reported";
  timestamp: string;
  interaction_kind: InteractionKind | null;
  risk: Severity | null;
}

export interface TimelineItem {
  timestamp: string;
  employee_id: string;
  text: string;
  source: "automatic" | "reported";
}

export interface ChecklistItem {
  /** C's stable item id; present on live incidents, absent in the generated mocks. */
  id?: string;
  /** C's step name, e.g. "revoke_sessions" (live only). */
  key?: string;
  action: string;
  rationale: string;
  done: boolean;
}

export interface Incident {
  id: string;
  type: string;
  severity: Severity;
  campaign_id: string | null;
  affected_employees: string[];
  evidence: Evidence[];
  checklist: ChecklistItem[];
  timeline: TimelineItem[];
  created_at: string;
}

export interface Campaign {
  id: string;
  name: string;
  message_ids: string[];
  recipients: string[];
  departments: string[];
  shared_traits: string[];
  updated_at: string;
  incident_id?: string | null;
}

export interface Interaction {
  message_id: string;
  employee_id: string;
  kind: InteractionKind;
}

// ------------------------------------------------- live API (backend only)

/** POST /api/sim/containment. Containment always needs an admin's approval. */
export interface ContainmentRequest {
  action: ContainmentActionType;
  campaign_id?: string | null;
  message_ids?: string[];
  employee_ids?: string[];
  sender?: string | null;
  domain?: string | null;
  approved_by: string;
}

export interface AttackStatus {
  scenario: string | null;
  running: boolean;
  speed: number;
  demo_seconds_elapsed: number;
  delivered_count: number;
  total_count: number;
  next_message_id: string | null;
  next_delivery_at_seconds: number | null;
}

export interface TrackedLink {
  token: string;
  message_id: string;
  employee_id: string;
  url: string;
}

/** GET /api/sim/inbox/{employee_id}: links are already rewritten to /r/{token}. */
export interface InboxMessage {
  id: string;
  sender_name: string;
  sender_address: string;
  reply_to: string | null;
  subject: string;
  body_text: string;
  body_html: string | null;
  links: TrackedLink[];
  attachments: { filename: string; content_type: string; size_bytes: number }[];
  delivered_at: string;
}

/** POST /api/interactions. */
export interface InteractionResult {
  guidance: string[];
  /** What the system already knew, e.g. ["link_clicked", "password_reuse"]. */
  already_detected: string[];
  incident: Incident | null;
}

/** Simulated Chrome PASSWORD_REUSE_EVENT. It never contains the password. */
export interface PasswordReuseEvent {
  event_type: "passwordReuseEvent";
  user: string;
  employee_id: string | null;
  url: string;
  domain: string;
  reused_credential: string;
  timestamp: string;
  simulated: boolean;
}

/** POST /api/analyze/signals. */
export interface SignalsResponse {
  message: Message;
  signals: Signal[];
  unchecked: string[];
}

/**
 * The named events on GET /api/events (the payload is JSON). "message.scored" carries
 * the Evidence row; "containment.done" and "recovery.updated" are declared in the
 * backend's hub but nothing publishes them yet, so the UI also refetches after its own actions.
 */
export interface LiveEventMap {
  "message.scored": Evidence;
  "incident.created": Incident;
  "incident.escalated": Incident;
  "incident.updated": Incident;
  "campaign.updated": Campaign;
  "containment.done": ContainmentResult[];
  "recovery.updated": RecoveryStatus;
}

export type LiveEventName = keyof LiveEventMap;
