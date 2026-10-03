import { SEVERITY_NAMES, type Severity } from "@/lib/contracts";

const STYLES = [
  "text-low bg-low/10 ring-low/30",
  "text-medium bg-medium/10 ring-medium/30",
  "text-high bg-high/10 ring-high/35",
  "text-critical bg-critical/12 ring-critical/40",
];

/** A risk level as a colored pill: LOW, MEDIUM, HIGH or CRITICAL. */
export function RiskBadge({ risk, size = "sm" }: { risk: Severity; size?: "sm" | "lg" }) {
  const sizing = size === "lg" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-[11px]";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-semibold tracking-wide ring-1 ring-inset ${sizing} ${STYLES[risk]}`}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {SEVERITY_NAMES[risk]}
    </span>
  );
}

/** Tailwind text color class for a risk level. */
export const RISK_TEXT = ["text-low", "text-medium", "text-high", "text-critical"] as const;
/** Tailwind background color class for a risk level. */
export const RISK_BG = ["bg-low", "bg-medium", "bg-high", "bg-critical"] as const;
