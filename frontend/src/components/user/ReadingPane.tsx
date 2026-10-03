"use client";

/**
 * One open email: the automatic warning, the header, "Is this safe?" with the risk
 * card and the decision flow, then the body rendered safely. A click on a link is
 * recorded first (like A's /r/{token} redirect) and only opens simulated demo pages.
 */

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { demoPageFor } from "@/lib/api";
import type { DeliveredEmail } from "@/lib/demo/selectors";
import { demoActions } from "@/lib/demo/store";
import { clockTime, fileSize, initials } from "@/components/ui/format";
import { DecisionFlow } from "./DecisionFlow";
import { RiskCard } from "./RiskCard";
import { SafeEmailBody } from "./SafeEmailBody";
import { WarningBanner } from "./WarningBanner";

interface Props {
  delivered: DeliveredEmail;
  employeeId: string;
  checked: boolean;
  onCheck: (show: boolean) => void;
  onBack?: () => void;
}

export function ReadingPane({ delivered, employeeId, checked, onCheck, onBack }: Props) {
  const router = useRouter();
  const { email, deliveredAt } = delivered;
  const { message, assessment } = email;
  const [blockedUrl, setBlockedUrl] = useState<string | null>(null);

  const onLink = useCallback(
    (url: string) => {
      const web = /^https?:\/\//i.test(url);
      if (web) demoActions.recordClick(employeeId, email.id, url); // recorded before anything opens
      const page = web ? demoPageFor(url, employeeId) : null;
      if (page?.startsWith("/demo/")) router.push(page);
      else setBlockedUrl(url);
    },
    [employeeId, email.id, router],
  );

  return (
    <article className="mx-auto max-w-3xl space-y-4 px-4 py-5 sm:px-6">
      {onBack && (
        <button type="button" onClick={onBack} className="text-sm font-medium text-accent md:hidden">
          ← Inbox
        </button>
      )}

      <WarningBanner assessment={assessment} onExplain={checked ? undefined : () => onCheck(true)} />

      <header className="space-y-3">
        <h1 className="text-xl font-semibold leading-snug text-ink">{message.subject}</h1>
        <div className="flex items-start gap-3">
          <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-panel-2 text-sm font-semibold text-muted ring-1 ring-line">
            {initials(message.sender_name || message.sender)}
          </span>
          <div className="min-w-0 flex-1 text-sm">
            <p className="text-ink">
              <span className="font-semibold">{message.sender_name || message.sender}</span>{" "}
              <span className="break-all text-muted">&lt;{message.sender}&gt;</span>
            </p>
            <p className="truncate text-muted">To: {message.recipients.join(", ")}</p>
            {message.reply_to && <p className="truncate text-muted">Reply to: {message.reply_to}</p>}
          </div>
          <time className="shrink-0 text-xs text-muted" dateTime={new Date(deliveredAt).toISOString()}>
            {clockTime(deliveredAt)}
          </time>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onCheck(!checked)}
            aria-expanded={checked}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              checked ? "border border-line bg-panel text-ink hover:bg-panel-2" : "bg-accent text-accent-ink hover:opacity-90"
            }`}
          >
            {checked ? "Hide the check" : "🛡 Is this safe?"}
          </button>
        </div>
      </header>

      {checked && (
        <div className="space-y-4 animate-slide-in">
          <RiskCard assessment={assessment} message={message} />
          <DecisionFlow key={email.id} employeeId={employeeId} messageId={email.id} />
        </div>
      )}

      {blockedUrl && (
        <p role="alert" className="rounded-lg border border-medium/40 bg-medium/10 px-4 py-3 text-sm text-ink">
          <span className="font-semibold">Link blocked:</span> this address is outside the demo, so it was not opened.
          <span className="mt-0.5 block break-all font-mono text-xs text-muted">{blockedUrl}</span>
        </p>
      )}

      <div className="rounded-xl border border-line bg-panel px-5 py-4">
        <SafeEmailBody html={message.body_html} text={message.body_text} onLink={onLink} />
      </div>

      {message.attachments.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            {message.attachments.length === 1 ? "1 attachment" : `${message.attachments.length} attachments`}
          </h2>
          <ul role="list" className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map((a) => (
              <li
                key={a.filename}
                title="Attachments are never opened in the demo"
                className="flex items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2 text-sm"
              >
                <span aria-hidden>📎</span>
                <span className="max-w-[16rem] truncate text-ink">{a.filename || "Unnamed file"}</span>
                <span className="text-xs text-muted">{fileSize(a.size_bytes)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
