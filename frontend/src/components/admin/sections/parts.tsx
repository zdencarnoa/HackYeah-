/**
 * Small building blocks shared by the admin detail sections. Dark console styles,
 * semantic tokens only.
 */

import type { ReactNode } from "react";

import { initials } from "@/components/ui/format";

/** A small uppercase label above a group of content. */
export function Heading({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{children}</h3>
      {right}
    </div>
  );
}

/** A bordered block inside a section. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-line bg-panel-2/60 p-4 ${className}`}>{children}</div>;
}

const STAT_TONES = {
  ink: "text-ink",
  critical: "text-critical",
  high: "text-high",
  medium: "text-medium",
  low: "text-low",
  muted: "text-muted",
} as const;

export type Tone = keyof typeof STAT_TONES;

/** A big number with a label under it. */
export function Stat({ value, label, tone = "ink" }: { value: ReactNode; label: string; tone?: Tone }) {
  return (
    <div className="min-w-0">
      <div className={`text-2xl font-semibold tabular-nums leading-none ${STAT_TONES[tone]}`}>{value}</div>
      <div className="mt-1.5 text-xs text-muted">{label}</div>
    </div>
  );
}

const CHIP_TONES = {
  neutral: "bg-panel text-ink ring-line",
  critical: "bg-critical/12 text-critical ring-critical/35",
  high: "bg-high/10 text-high ring-high/30",
  medium: "bg-medium/10 text-medium ring-medium/30",
  low: "bg-low/10 text-low ring-low/30",
  accent: "bg-accent/12 text-accent ring-accent/30",
  sim: "bg-sim/12 text-sim ring-sim/30",
} as const;

export type ChipTone = keyof typeof CHIP_TONES;

export function Chip({ children, tone = "neutral" }: { children: ReactNode; tone?: ChipTone }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${CHIP_TONES[tone]}`}>
      {children}
    </span>
  );
}

/** A round avatar with initials; colored ring when the person is at risk. */
export function Avatar({ name, tone = "neutral" }: { name: string; tone?: ChipTone }) {
  return (
    <span
      aria-hidden
      className={`grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold ring-1 ring-inset ${CHIP_TONES[tone]}`}
    >
      {initials(name)}
    </span>
  );
}

/** Severity 0–3 as filled dots, for signal strength. */
export function SeverityDots({ severity }: { severity: number }) {
  const color = ["bg-muted", "bg-medium", "bg-high", "bg-critical"][severity] ?? "bg-muted";
  return (
    <span className="inline-flex gap-0.5" aria-label={`Strength ${severity} of 3`} title={`Strength ${severity} of 3`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`size-1.5 rounded-full ${i <= severity ? color : "bg-line"}`} />
      ))}
    </span>
  );
}
