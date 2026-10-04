import type { ReactNode } from "react";

/**
 * Browser-like chrome around a simulated site: a fake address bar, so the audience
 * sees which address the page really lives on, and a small "simulated page" footer.
 */
export function SiteFrame({ pageUrl, children }: { pageUrl: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#f3f3f3]">
      <FakeAddressBar pageUrl={pageUrl} />
      <div className="flex flex-1 flex-col">{children}</div>
      <SimulatedFooter />
    </div>
  );
}

function FakeAddressBar({ pageUrl }: { pageUrl: string }) {
  return (
    <div className="flex items-center gap-3 border-b border-[#d7d7d7] bg-[#e9e9eb] px-3 py-2 text-[13px] text-[#3c3c3c]">
      <div aria-hidden className="flex gap-1.5">
        <span className="size-3 rounded-full bg-[#ff5f57]" />
        <span className="size-3 rounded-full bg-[#febc2e]" />
        <span className="size-3 rounded-full bg-[#28c840]" />
      </div>
      <div aria-hidden className="flex gap-2 text-[#8a8a8a]">
        <span>←</span>
        <span>→</span>
        <span>↻</span>
      </div>
      <div
        className="flex min-w-0 flex-1 items-center gap-2 rounded-full bg-white px-3 py-1 shadow-[inset_0_0_0_1px_#dcdcdc]"
        aria-label="Address of this page"
      >
        <LockIcon />
        <span className="truncate font-mono text-[12.5px]" title={pageUrl}>
          {pageUrl}
        </span>
      </div>
    </div>
  );
}

function LockIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-3.5 shrink-0 fill-[#5f6368]">
      <path d="M4.5 7V5.5a3.5 3.5 0 1 1 7 0V7H12a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h.5Zm1.5 0h4V5.5a2 2 0 1 0-4 0V7Z" />
    </svg>
  );
}

export function SimulatedFooter() {
  return (
    <footer className="px-4 py-3 text-center text-[11px] text-[#8a8a8a]">
      Security Copilot demo · simulated page
    </footer>
  );
}
