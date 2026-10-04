"use client";

/**
 * Hidden demo controls on the employee window (team plan: switch persona). Press D
 * to show or hide it. Launching and resetting the attack live in the admin bar.
 */

import { useEffect, useState } from "react";

import { CAMPAIGNS, EMPLOYEE_BY_EMAIL } from "@/lib/mocks";

// Employees worth switching to: everyone the demo campaign reached.
const CAMPAIGN_RECIPIENTS = [...new Set(CAMPAIGNS.flatMap((c) => c.recipients))]
  .map((address) => EMPLOYEE_BY_EMAIL[address])
  .filter(Boolean);

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function UserDemoBar({ employeeId }: { employeeId: string }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== "d" || event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      setOpen((value) => !value);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;
  return (
    <div
      role="region"
      aria-label="Demo controls"
      className="fixed inset-x-0 bottom-0 z-50 flex flex-wrap items-center gap-3 border-t border-line bg-panel px-4 py-2 text-xs text-muted shadow-lg"
    >
      <span className="font-semibold text-ink">Demo</span>
      <span className="flex items-center gap-1" role="group" aria-label="Switch persona">
        Persona:
        <a href="/admin" className="rounded-md px-2 py-1 text-ink ring-1 ring-inset ring-line hover:bg-panel-2">
          Admin
        </a>
        {CAMPAIGN_RECIPIENTS.map((employee) => (
          <a
            key={employee.id}
            href={`/user?as=${employee.id}`}
            aria-current={employee.id === employeeId ? "page" : undefined}
            className={
              employee.id === employeeId
                ? "rounded-md bg-accent px-2 py-1 font-semibold text-accent-ink"
                : "rounded-md px-2 py-1 text-ink ring-1 ring-inset ring-line hover:bg-panel-2"
            }
          >
            {employee.name.split(" ")[0]}
          </a>
        ))}
      </span>
      <span className="ml-auto">All data and actions are simulated · press D to hide</span>
    </div>
  );
}
