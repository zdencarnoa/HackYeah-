/**
 * The answer to "Is this safe?": the risk level, the reasons in plain words, the
 * next step, and what could not be checked. Technical evidence waits in the
 * collapsed "Advanced details" drawer.
 */

import { Severity, type Assessment, type Message, type Signal } from "@/lib/contracts";
import { RiskBadge, RISK_TEXT } from "@/components/ui/RiskBadge";

export function RiskCard({ assessment, message }: { assessment: Assessment; message: Message | null }) {
  const reasons = assessment.explanation.reasons.length
    ? assessment.explanation.reasons
    : assessment.signals.filter((s) => s.severity >= 1).slice(0, 5).map((s) => s.evidence);
  const urgent = assessment.risk >= Severity.HIGH;
  return (
    <section aria-label="Security Copilot check" className="rounded-xl border border-line bg-panel shadow-sm">
      <header className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">Security Copilot check</span>
        <RiskBadge risk={assessment.risk} size="lg" />
        <p className={`w-full text-base font-semibold ${RISK_TEXT[assessment.risk]}`}>{assessment.explanation.summary}</p>
      </header>

      <div className="space-y-5 px-5 py-4">
        {reasons.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-ink">Why</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-ink">
              {reasons.map((reason) => (
                <li key={reason} className="flex gap-2">
                  <span aria-hidden className={`mt-1.5 size-1.5 shrink-0 rounded-full ${urgent ? "bg-critical" : "bg-muted"}`} />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {assessment.uncertainties.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-ink">What we could not check</h3>
            <ul className="mt-1.5 space-y-1 text-sm text-muted">
              {assessment.uncertainties.map((u) => <li key={u}>{u}</li>)}
            </ul>
            <p className="mt-1.5 text-xs text-muted">This does not prove the email is safe or dangerous.</p>
          </div>
        )}

        <div className={`rounded-lg px-4 py-3 ${urgent ? "bg-critical/10" : "bg-accent/10"}`}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">What to do now</h3>
          <p className="mt-1 text-sm font-semibold text-ink">{assessment.recommended_action}</p>
        </div>

        <p className="text-xs text-muted">
          The risk level comes from fixed security checks and a text model.
          {assessment.explanation.source === "llm"
            ? " The wording above was written by AI from that evidence only."
            : " The wording above comes from a fixed template."}
        </p>

        <AdvancedDetails assessment={assessment} message={message} />
      </div>
    </section>
  );
}

function AdvancedDetails({ assessment, message }: { assessment: Assessment; message: Message | null }) {
  const auth = message?.headers.filter(([name]) => name.toLowerCase() === "authentication-results").map(([, v]) => v) ?? [];
  return (
    <details className="rounded-lg border border-line bg-panel-2">
      <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-medium text-ink">
        Advanced details
        <span className="ml-2 text-xs font-normal text-muted">technical evidence for IT</span>
      </summary>
      <div className="space-y-4 border-t border-line px-4 py-3 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted">Risk score</dt>
          <dd className="font-mono">{assessment.score}</dd>
          <dt className="text-muted">Text model</dt>
          <dd className="font-mono">
            {assessment.ml_confidence === null
              ? "not available"
              : `${Math.round(assessment.ml_confidence * 100)}% phishing-like (${assessment.ml_model ?? "model"})`}
          </dd>
        </dl>

        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">Signals ({assessment.signals.length})</h4>
          <ul className="mt-2 space-y-2">
            {assessment.signals.map((signal) => <SignalRow key={signal.id} signal={signal} />)}
          </ul>
        </div>

        {auth.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">Authentication-Results</h4>
            {auth.map((value, i) => (
              <p key={i} className="mt-1 break-all rounded bg-panel px-2 py-1 font-mono text-xs text-ink">{value}</p>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  return (
    <li className="rounded-md border border-line bg-panel px-3 py-2">
      <div className="flex items-start gap-2">
        <SeverityDots severity={signal.severity} />
        <p className="flex-1 text-ink">{signal.evidence}</p>
        <span className="rounded bg-panel-2 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted">{signal.source}</span>
      </div>
      <p className="mt-1 break-all pl-[3.25rem] font-mono text-xs text-muted">
        {signal.category} · {signal.technical_detail}
      </p>
    </li>
  );
}

/** Signal strength 0-3 as dots: context, weak, moderate, strong. */
function SeverityDots({ severity }: { severity: Signal["severity"] }) {
  const color = severity >= 3 ? "bg-critical" : severity === 2 ? "bg-high" : severity === 1 ? "bg-medium" : "bg-muted";
  const label = ["context only", "weak", "moderate", "strong"][severity];
  return (
    <span role="img" aria-label={`Signal strength: ${label}`} title={`Signal strength: ${label}`} className="mt-1.5 flex w-11 shrink-0 gap-1">
      {[1, 2, 3].map((n) => (
        <span key={n} className={`size-2 rounded-full ${n <= severity ? color : "bg-line"}`} />
      ))}
    </span>
  );
}
