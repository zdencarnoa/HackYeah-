"use client";

/**
 * The verdict on one email: B's risk level and plain-language reasons first, then
 * the recommended action and what could not be verified. Signals, the classifier
 * score and the fusion score sit under "Advanced details".
 */

import { RiskBadge } from "@/components/ui/RiskBadge";
import { riskName, type FlaggedEmail } from "@/lib/demo/selectors";
import type { Signal } from "@/lib/contracts";

import { Heading, Panel, SeverityDots } from "./parts";

const SOURCE_LABEL: Record<Signal["source"], string> = {
  rule: "Rule",
  url: "Link check",
  ml: "Text classifier",
  intel: "Blocklist",
};

export function AssessmentSection({ email }: { email: FlaggedEmail }) {
  const assessment = email.email.assessment;
  const raisedBecause = raisedReason(email);
  const signals = assessment.signals.slice().sort((a, b) => b.severity - a.severity);
  const authResults = email.email.message.headers.find(([name]) => name.toLowerCase() === "authentication-results")?.[1];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start gap-3">
        <RiskBadge risk={email.risk} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-medium leading-snug text-ink">{assessment.explanation.summary}</p>
          {raisedBecause && (
            <p className="mt-1 text-xs text-critical">
              Raised from {riskName(assessment.risk)} on arrival: {raisedBecause}.
            </p>
          )}
        </div>
      </header>

      <section>
        <Heading>Why this email is suspicious</Heading>
        <ol className="space-y-2">
          {assessment.explanation.reasons.map((reason, i) => (
            <li key={i} className="flex gap-3 text-sm leading-relaxed text-ink">
              <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-panel text-[11px] font-semibold text-muted ring-1 ring-line">
                {i + 1}
              </span>
              <span>{reason}</span>
            </li>
          ))}
        </ol>
      </section>

      <Panel className="border-accent/30 bg-accent/5">
        <Heading>Recommended action</Heading>
        <p className="text-sm leading-relaxed text-ink">{assessment.recommended_action}</p>
      </Panel>

      {assessment.uncertainties.length > 0 && (
        <section>
          <Heading>What we could not verify</Heading>
          <ul className="space-y-1.5">
            {assessment.uncertainties.map((text, i) => (
              <li key={i} className="flex gap-2 text-sm text-muted">
                <span aria-hidden className="text-medium">?</span>
                {text}
              </li>
            ))}
          </ul>
        </section>
      )}

      <details className="group rounded-xl border border-line bg-panel-2/40">
        <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium text-ink">
          Advanced details
          <span aria-hidden className="text-muted transition-transform group-open:rotate-90">›</span>
        </summary>
        <div className="space-y-5 border-t border-line px-4 py-4">
          <section>
            <Heading>Signals ({signals.length})</Heading>
            <ul className="divide-y divide-line">
              {signals.map((signal) => (
                <li key={signal.id} className="py-2.5">
                  <div className="flex items-center gap-2 text-xs">
                    <SeverityDots severity={signal.severity} />
                    <span className="font-medium text-ink">{signal.category.replaceAll("_", " ")}</span>
                    <span className="text-muted">· {SOURCE_LABEL[signal.source]}</span>
                  </div>
                  <p className="mt-1 text-sm text-ink">{signal.evidence}</p>
                  <p className="mt-1 break-words font-mono text-[11px] text-muted">{signal.technical_detail}</p>
                </li>
              ))}
            </ul>
          </section>

          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted">Text classifier</dt>
              <dd className="mt-0.5 font-mono text-ink">
                {assessment.ml_confidence === null
                  ? "not available"
                  : `${(assessment.ml_confidence * 100).toFixed(2)}% (${assessment.ml_model ?? "unknown model"})`}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Fusion score</dt>
              <dd className="mt-0.5 font-mono text-ink">{assessment.score}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Explanation written by</dt>
              <dd className="mt-0.5 text-ink">
                {assessment.explanation.source === "llm" ? "AI, from the signals above" : "Template (no AI)"}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-muted">
            The text classifier can raise the risk but never sets HIGH or above on its own. The risk level comes
            from the rules and signals; the AI only explains them.
          </p>

          {authResults && (
            <section>
              <Heading>Authentication results</Heading>
              <p className="break-words font-mono text-[11px] text-muted">{authResults}</p>
            </section>
          )}
        </div>
      </details>
    </div>
  );
}

/** Why the shown risk is higher than the score on arrival, in plain words. */
function raisedReason(email: FlaggedEmail): string | null {
  if (email.risk <= email.email.assessment.risk) return null;
  if (email.passwordBy.length) return "a password was entered on an unapproved site after a click";
  if (email.reports.some((r) => r.interaction === "password" || r.interaction === "other_info")) {
    return "a recipient reported entering their details";
  }
  if (email.clickedBy.length) return "a recipient clicked the link";
  return "a recipient reported interacting with it";
}
