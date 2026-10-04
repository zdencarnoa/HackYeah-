import type { CampaignView } from "@/lib/demo/selectors";
import { SimulationBadge } from "@/components/ui/SimulationBadge";

type Status = "forming" | "active" | "contained";

function statusOf(view: CampaignView): Status {
  if (view.contained) return "contained";
  return view.delivered.length < view.campaign.message_ids.length ? "forming" : "active";
}

const STATUS_STYLE: Record<Status, string> = {
  forming: "text-high ring-high/35",
  active: "text-critical ring-critical/40",
  contained: "text-low ring-low/30",
};

const STATUS_LABEL: Record<Status, string> = {
  forming: "Forming",
  active: "Active",
  contained: "Contained",
};

/** Active campaigns (idea.md §9): related messages grouped, not judged one by one. */
export function CampaignStrip({ campaigns, onOpen }: { campaigns: CampaignView[]; onOpen: (view: CampaignView) => void }) {
  if (campaigns.length === 0) return null;
  return (
    <section aria-label="Campaigns" className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Campaigns</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {campaigns.map((view) => {
          const status = statusOf(view);
          return (
            <button
              key={view.campaign.id}
              type="button"
              onClick={() => onOpen(view)}
              className="group rounded-xl border border-line bg-panel px-4 py-3 text-left transition hover:border-accent/50 hover:bg-panel-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">{view.campaign.name}</p>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${STATUS_STYLE[status]}`}>
                  {STATUS_LABEL[status]}
                </span>
                {status === "contained" && <SimulationBadge />}
                <span className="ml-auto text-xs text-accent opacity-0 transition group-hover:opacity-100">Open →</span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {count(view.delivered.length, "message")} · {count(view.recipientsReached.length, "recipient")} ·{" "}
                {count(view.departmentsReached.length, "department")}
                {view.senderDomains.length > 0 && <> · from {view.senderDomains.join(", ")}</>}
              </p>
              <p className="mt-1 text-sm">
                <span className={view.clicks ? "text-high" : "text-muted"}>{count(view.clicks, "employee")} clicked</span>
                <span className="text-muted"> · </span>
                <span className={view.credentialSubmissions ? "font-semibold text-critical" : "text-muted"}>
                  {count(view.credentialSubmissions, "password")} entered
                </span>
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function count(n: number, noun: string): string {
  return `${n} ${n === 1 ? noun : `${noun}s`}`;
}
