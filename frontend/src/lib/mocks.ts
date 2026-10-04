/**
 * Mock data generated from the real backend (scripts/generate_mocks.py): D's demo
 * mail and org, run through A's detection and B's analyze(). Campaigns stand in for
 * C's correlation until C's API exists.
 */

import campaignsJson from "@/mocks/campaigns.json";
import mailJson from "@/mocks/mail.json";
import orgJson from "@/mocks/org.json";

import type { Assessment, Campaign, Employee, Message, Organization } from "./contracts";

export interface DemoEmail {
  id: string;
  /** Seconds after demo start at which D's attack engine delivers it. */
  deliver_offset_s: number;
  recipient_ids: string[];
  message: Message;
  assessment: Assessment;
}

export const ORG = orgJson as unknown as Organization;
export const EMAILS = (mailJson.emails as unknown as DemoEmail[])
  .slice()
  .sort((a, b) => a.deliver_offset_s - b.deliver_offset_s);
export const CAMPAIGNS = campaignsJson as unknown as Campaign[];
export const MOCKS_GENERATED_FROM = mailJson.generated_from;

export const EMAIL_BY_ID: Record<string, DemoEmail> = Object.fromEntries(EMAILS.map((e) => [e.id, e]));
export const EMPLOYEE_BY_ID: Record<string, Employee> = Object.fromEntries(ORG.employees.map((e) => [e.id, e]));
export const EMPLOYEE_BY_EMAIL: Record<string, Employee> = Object.fromEntries(
  ORG.employees.map((e) => [e.email, e]),
);

export const DEMO_EMPLOYEE_ID = "e01"; // Alice Johnson, Finance
export const ADMIN_EMPLOYEE_ID = ORG.employees.find((e) => e.is_admin)?.id ?? "e15";

export function campaignOf(messageId: string): Campaign | undefined {
  return CAMPAIGNS.find((c) => c.message_ids.includes(messageId));
}
