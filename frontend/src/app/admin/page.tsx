import type { Metadata } from "next";

import { AdminConsole } from "@/components/admin/AdminConsole";
import { ClientOnly } from "@/components/ui/ClientOnly";

export const metadata: Metadata = {
  title: "Admin console · Security Copilot",
};

export default function AdminPage() {
  return (
    <div data-theme="dark" className="min-h-screen bg-bg text-ink">
      <ClientOnly fallback={<p className="p-8 text-sm text-muted">Loading the security console…</p>}>
        <AdminConsole />
      </ClientOnly>
    </div>
  );
}
