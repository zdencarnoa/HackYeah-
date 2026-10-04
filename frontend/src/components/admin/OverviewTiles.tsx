import type { CampaignView, FlaggedEmail } from "@/lib/demo/selectors";

interface Tile {
  label: string;
  value: number | string;
  /** Text color when the number means risk; neutral otherwise. */
  tone: string;
  hint: string;
}

/** Security overview (idea.md §10): the few numbers an admin acts on. */
export function OverviewTiles({
  flagged,
  campaigns,
  compromised,
}: {
  flagged: FlaggedEmail[];
  campaigns: CampaignView[];
  compromised: string[];
}) {
  const dangerous = flagged.filter((f) => f.level === "dangerous");
  const warnings = flagged.filter((f) => f.level === "warning");
  const reached = new Set(dangerous.flatMap((f) => f.email.recipient_ids));
  const exposed = new Set(flagged.flatMap((f) => f.clickedBy));
  const contained = campaigns.filter((c) => c.contained).length;

  const tiles: Tile[] = [
    { label: "Dangerous emails", value: dangerous.length, tone: dangerous.length ? "text-high" : "", hint: "Scored HIGH or CRITICAL" },
    { label: "Warnings", value: warnings.length, tone: warnings.length ? "text-medium" : "", hint: "Scored MEDIUM: worth a look" },
    { label: "Employees reached", value: reached.size, tone: "", hint: "Received at least one dangerous email" },
    { label: "Possible exposures", value: exposed.size, tone: exposed.size ? "text-high" : "", hint: "Clicked a link in a flagged email" },
    {
      label: "Accounts at risk",
      value: compromised.length,
      tone: compromised.length ? "text-critical" : "",
      hint: "Password on an unapproved site, unusual sign-in or own report",
    },
    {
      label: "Campaigns contained",
      value: campaigns.length ? `${contained}/${campaigns.length}` : 0,
      tone: campaigns.length && contained === campaigns.length ? "text-low" : "",
      hint: "Simulated containment approved",
    },
  ];

  return (
    <section aria-label="Security overview" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-xl border border-line bg-panel px-4 py-3" title={tile.hint}>
          <p className={`text-3xl font-semibold tabular-nums ${tile.tone}`}>{tile.value}</p>
          <p className="mt-1 text-xs text-muted">{tile.label}</p>
        </div>
      ))}
    </section>
  );
}
