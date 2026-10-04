"use client";

/**
 * The live detail sections for one incident: campaign, blast radius, containment
 * and recovery, each reading the backend and showing its errors in plain words.
 * Containment is only ever simulated, and always waits for the admin's approval.
 */

import { useCallback, useEffect, useState } from "react";

import { clockTime } from "@/components/ui/format";
import { SimulationBadge } from "@/components/ui/SimulationBadge";
import { liveApi, type ApiResult } from "@/lib/api";
import type { BlastRadius, Campaign, ContainmentResult, Incident, RecoveryStatus, RecoveryTrack } from "@/lib/contracts";
import { ADMIN_EMPLOYEE_ID, EMPLOYEE_BY_ID } from "@/lib/mocks";

import { BlastRadiusSection } from "../sections/BlastRadiusSection";
import { Chip, Heading, Panel } from "../sections/parts";

const MAX_DETAILS = 4;
/** Backend checklist items the admin ticks by hand; the rest follow from containment. */
const MANUAL_ITEMS = new Set(["review_account_activity", "confirm_password_reset", "complete_incident_report"]);

const name = (id: string) => EMPLOYEE_BY_ID[id]?.name ?? id;

/** Accounts the evidence says are likely compromised (password typed, unusual sign-in, or reported). */
export function compromisedIn(incident: Incident): string[] {
  const ids = incident.evidence
    .filter(
      (e) =>
        e.kind === "password_reuse" ||
        e.kind === "unusual_signin" ||
        (e.kind === "user_report" && (e.interaction_kind === "password" || e.interaction_kind === "other_info")),
    )
    .map((e) => e.employee_id);
  return [...new Set(ids)];
}

function messageIdsOf(incident: Incident, campaign: Campaign | undefined): string[] {
  if (campaign) return campaign.message_ids;
  return [...new Set(incident.evidence.flatMap((e) => (e.message_id ? [e.message_id] : [])))];
}

/** Runs `load` on mount and whenever `refreshKey` changes. Failures become `error`, never a blank panel. */
function useLoaded<T>(load: () => Promise<ApiResult<T>>, refreshKey: unknown) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  useEffect(() => {
    let cancelled = false;
    load().then((result) => {
      if (cancelled) return;
      setState(result.ok ? { data: result.data, error: null, loading: false } : { data: null, error: result.error, loading: false });
    });
    return () => {
      cancelled = true;
    };
  }, [load, refreshKey]);
  return { ...state, set: (data: T) => setState({ data, error: null, loading: false }) };
}

function Unavailable({ what, error }: { what: string; error: string }) {
  return (
    <Panel className="border-medium/40 bg-medium/10">
      <p className="text-sm font-medium text-medium">Live {what} is unavailable.</p>
      <p className="mt-0.5 text-xs text-muted">{error} This does not mean there is nothing to see; try again in a moment.</p>
    </Panel>
  );
}

// ---------------------------------------------------------------- campaign

export function LiveCampaign({ campaign }: { campaign: Campaign }) {
  return (
    <div className="space-y-5">
      <header>
        <Heading>Campaign</Heading>
        <h2 className="text-lg font-semibold">{campaign.name}</h2>
        <p className="mt-0.5 text-xs text-muted">
          {campaign.message_ids.length} messages · {campaign.recipients.length} recipients
          {campaign.departments.length > 0 && ` · ${campaign.departments.join(", ")}`}
        </p>
      </header>
      {campaign.shared_traits.length > 0 && (
        <section>
          <Heading>Why these messages are grouped</Heading>
          <ul className="space-y-1 text-sm">
            {campaign.shared_traits.map((trait) => (
              <li key={trait} className="flex gap-2"><span aria-hidden className="text-muted">·</span>{trait}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">Grouping shows similarity, not proof. Check the evidence before acting on every recipient.</p>
        </section>
      )}
      <section>
        <Heading>Reached</Heading>
        <div className="flex flex-wrap gap-1.5">
          {campaign.recipients.map((id) => <Chip key={id}>{name(id)}</Chip>)}
        </div>
      </section>
    </div>
  );
}

// ------------------------------------------------------------ blast radius

export function LiveBlastRadius({ incident }: { incident: Incident }) {
  const candidates = incident.affected_employees;
  const atRisk = compromisedIn(incident)[0];
  const [chosen, setChosen] = useState<string | null>(null);
  const employeeId = chosen ?? atRisk ?? candidates[0];
  const load = useCallback(() => (employeeId ? liveApi.blastRadius(employeeId) : Promise.resolve<ApiResult<BlastRadius>>({ ok: false, error: "No affected employee yet.", status: null })), [employeeId]);
  const { data, error, loading } = useLoaded<BlastRadius>(load, employeeId);

  if (!employeeId) return <p className="text-sm text-muted">No affected employee is known for this incident yet.</p>;
  return (
    <div className="space-y-4">
      {candidates.length > 1 && (
        <label className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Show what this account can reach:</span>
          <select value={employeeId} onChange={(e) => setChosen(e.target.value)} className="rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-ink">
            {candidates.map((id) => (
              <option key={id} value={id}>{name(id)}{compromisedIn(incident).includes(id) ? " (account at risk)" : ""}</option>
            ))}
          </select>
        </label>
      )}
      {loading && <p className="text-sm text-muted">Loading what this account can reach…</p>}
      {error && <Unavailable what="blast radius" error={error} />}
      {data && (
        <>
          <p className="text-sm">{data.explanation}</p>
          <BlastRadiusSection key={employeeId} employeeId={employeeId} radius={data} />
          <ul className="space-y-1 text-xs text-muted">
            {data.nodes.filter((n) => n.at_risk && n.kind !== "employee" && n.reason).map((n) => (
              <li key={n.id}><span className="text-ink">{n.label}:</span> {n.reason}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------- containment

export function LiveContainment({
  incident,
  campaign,
  results,
  onResults,
}: {
  incident: Incident;
  campaign: Campaign | undefined;
  results: ContainmentResult[] | undefined;
  onResults: (results: ContainmentResult[]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const messageIds = messageIdsOf(incident, campaign);
  const compromised = compromisedIn(incident);

  async function approve() {
    setBusy(true);
    setError(null);
    const result = await liveApi.contain({
      action: "contain_campaign",
      campaign_id: incident.campaign_id,
      message_ids: messageIds,
      employee_ids: compromised,
      approved_by: ADMIN_EMPLOYEE_ID,
    });
    if (result.ok) onResults(result.data);
    else setError(result.status === 400 ? `${result.error} The messages may not have been delivered yet.` : result.error);
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-md">
          <Heading>Recommended containment</Heading>
          <p className="text-xs leading-relaxed text-muted">
            Nothing runs until you approve it. Every action is simulated: nothing touches real accounts, mailboxes or infrastructure.
          </p>
        </div>
        {!results && (
          <button
            type="button"
            onClick={approve}
            disabled={busy || messageIds.length === 0}
            className="shrink-0 rounded-lg bg-critical px-4 py-2 text-sm font-semibold text-bg shadow-[0_0_24px_-8px_var(--critical)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Working…" : incident.campaign_id ? "Contain campaign" : "Approve containment"}
          </button>
        )}
      </div>

      {!results && (
        <Panel>
          <p className="text-sm">This would, in simulation:</p>
          <ul className="mt-1.5 space-y-0.5 text-xs text-muted">
            <li>· Quarantine {messageIds.length} {messageIds.length === 1 ? "message" : "messages"}</li>
            <li>· Block the sender and the sending domain</li>
            <li>· Notify everyone who received them</li>
            {compromised.length > 0 && <li>· Revoke sessions and require a password reset for {compromised.map(name).join(", ")}</li>}
            <li>· Start an investigation</li>
          </ul>
          {messageIds.length === 0 && <p className="mt-2 text-xs text-medium">No message is linked to this incident yet, so there is nothing to contain.</p>}
        </Panel>
      )}

      {error && <p role="alert" className="text-sm text-critical">{error}</p>}

      {results && (
        <ul className="divide-y divide-line rounded-xl border border-line bg-panel-2/40">
          {results.map((r, i) => (
            <li key={`${r.action}-${i}`} className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <SimulationBadge />
                <span className="text-sm font-medium">{r.summary}</span>
                <span className="ml-auto font-mono text-[11px] text-muted">{clockTime(r.at)}</span>
              </div>
              {r.details.length > 0 && (
                <ul className="mt-1.5 space-y-0.5 pl-1 text-xs text-muted">
                  {(open ? r.details : r.details.slice(0, MAX_DETAILS)).map((d, j) => <li key={j} className="truncate" title={d}>· {d}</li>)}
                </ul>
              )}
              {r.details.length > MAX_DETAILS && (
                <button type="button" onClick={() => setOpen(!open)} className="mt-1 text-xs text-accent hover:underline">
                  {open ? "Show less" : `Show ${r.details.length - MAX_DETAILS} more`}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {results && <p className="flex items-center gap-2 text-sm text-low"><span aria-hidden>✓</span> Approved. Track progress under Recovery.</p>}
    </div>
  );
}

// ---------------------------------------------------------------- recovery

export function LiveRecovery({ refreshKey }: { refreshKey: unknown }) {
  const { data, error, loading, set } = useLoaded<RecoveryStatus>(liveApi.recovery, refreshKey);
  const [itemError, setItemError] = useState<string | null>(null);

  async function tick(itemId: string) {
    setItemError(null);
    const result = await liveApi.completeRecoveryItem(itemId);
    if (result.ok) set(result.data);
    else setItemError(result.error);
  }

  if (loading) return <p className="text-sm text-muted">Loading recovery status…</p>;
  if (error || !data) return <Unavailable what="recovery status" error={error ?? "No data."} />;

  const allDone = data.remaining_actions.length === 0 && data.tracks.every((t) => t.percent === 100);
  return (
    <div className="space-y-5">
      <Heading right={<SimulationBadge />}>Recovery status</Heading>
      {allDone && (
        <Panel className="border-low/40 bg-low/10">
          <p className="text-sm font-medium text-low">✓ All done. The incident can be closed.</p>
          <p className="mt-0.5 text-xs text-muted">Keep an eye on the account for a few days; recovery does not prove nothing was taken.</p>
        </Panel>
      )}
      <ul className="space-y-3">{data.tracks.map((t) => <TrackBar key={t.name} track={t} />)}</ul>
      {data.remaining_actions.length > 0 && (
        <section>
          <Heading>Remaining actions</Heading>
          <ul className="divide-y divide-line rounded-xl border border-line bg-panel-2/40">
            {data.remaining_actions.map((item) => {
              const manual = MANUAL_ITEMS.has(item.id);
              return (
                <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
                  <input
                    id={`live-recovery-${item.id}`}
                    type="checkbox"
                    checked={item.done}
                    disabled={!manual}
                    onChange={() => void tick(item.id)}
                    className="size-4 shrink-0 accent-low disabled:opacity-40"
                  />
                  <label htmlFor={`live-recovery-${item.id}`} className={`text-sm text-ink ${manual ? "cursor-pointer" : ""}`}>
                    {item.label}
                    {!manual && <span className="ml-2 text-xs text-muted">(done by containment)</span>}
                  </label>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {itemError && <p role="alert" className="text-sm text-critical">{itemError}</p>}
    </div>
  );
}

function TrackBar({ track }: { track: RecoveryTrack }) {
  const color = track.percent === 100 ? "bg-low" : track.percent >= 50 ? "bg-accent" : track.percent > 0 ? "bg-medium" : "bg-line";
  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span>{track.name}</span>
        <span className={`font-mono text-xs tabular-nums ${track.percent === 100 ? "text-low" : "text-muted"}`}>{track.percent}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-panel" role="progressbar" aria-label={track.name} aria-valuenow={track.percent} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${color}`} style={{ width: `${track.percent}%` }} />
      </div>
    </li>
  );
}
