import { Suspense } from "react";

import { ClientOnly } from "@/components/ui/ClientOnly";
import { Mailbox } from "@/components/user/Mailbox";

export const metadata = { title: "Mail · Security Copilot demo" };

/** The employee's mailbox. The demo state lives in the browser, so it renders client-side only. */
export default function UserPage() {
  const loading = <p className="p-6 text-sm text-muted">Loading mail…</p>;
  return (
    <div data-theme="light" className="min-h-dvh bg-bg text-ink">
      <Suspense fallback={loading}>
        <ClientOnly fallback={loading}>
          <Mailbox />
        </ClientOnly>
      </Suspense>
    </div>
  );
}
