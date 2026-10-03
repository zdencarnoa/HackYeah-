/** Every simulated action is labeled as such (CLAUDE.md: containment is never real). */
export function SimulationBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md bg-sim/12 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sim ring-1 ring-inset ring-sim/30 ${className}`}
    >
      ✓ Simulation
    </span>
  );
}
