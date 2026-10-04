/**
 * The automatic warning every scored email gets on arrival: nobody has to ask.
 * HIGH and CRITICAL get a clear "dangerous" banner, MEDIUM a softer "be careful".
 */

import { Severity, type Assessment } from "@/lib/contracts";

export function WarningBanner({ assessment, onExplain }: { assessment: Assessment; onExplain?: () => void }) {
  if (assessment.risk < Severity.MEDIUM) return null;
  const dangerous = assessment.risk >= Severity.HIGH;
  const tone = dangerous ? "border-critical/40 bg-critical/10" : "border-medium/40 bg-medium/10";
  return (
    <div role="note" className={`flex gap-3 rounded-lg border px-4 py-3 ${tone}`}>
      <span aria-hidden className={`mt-0.5 text-lg leading-none ${dangerous ? "text-critical" : "text-medium"}`}>
        {dangerous ? "⛔" : "⚠"}
      </span>
      <div className="min-w-0 flex-1 text-sm">
        <p className={`font-semibold ${dangerous ? "text-critical" : "text-medium"}`}>
          {dangerous ? "Security Copilot: this email looks dangerous." : "Be careful: parts of this email look unusual."}
        </p>
        <p className="mt-0.5 text-ink">{assessment.explanation.summary}</p>
        <p className="mt-0.5 font-medium text-ink">
          {dangerous ? "Do not click links or open attachments." : "Check the sender before you click anything."}
        </p>
      </div>
      {onExplain && (
        <button
          type="button"
          onClick={onExplain}
          className="self-start whitespace-nowrap rounded-md border border-line bg-panel px-3 py-1.5 text-sm font-medium text-ink hover:bg-panel-2"
        >
          See why
        </button>
      )}
    </div>
  );
}

/** The small version shown in the message list. */
export function RiskTag({ assessment }: { assessment: Assessment }) {
  if (assessment.risk < Severity.MEDIUM) return null;
  const dangerous = assessment.risk >= Severity.HIGH;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${
        dangerous ? "bg-critical/10 text-critical" : "bg-medium/10 text-medium"
      }`}
    >
      <span aria-hidden>{dangerous ? "⛔" : "⚠"}</span>
      {dangerous ? "Dangerous" : "Be careful"}
    </span>
  );
}
