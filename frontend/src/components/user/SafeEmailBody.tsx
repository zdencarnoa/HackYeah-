"use client";

/**
 * Renders an email body without trusting it. body_html is written by whoever sent
 * the email, so it is never injected as HTML: it is parsed into an inert document
 * (DOMParser runs no scripts and loads no images), and only an allowlist of plain
 * formatting tags is rebuilt as React elements, with every attribute dropped except
 * a link's address. Links become buttons that go through `onLink`, so a click is
 * recorded before anything opens.
 */

import { Fragment, createElement, useMemo, type ReactNode } from "react";

/** Tags rebuilt as-is. Anything else is unwrapped (its text kept) or dropped. */
const ALLOWED = new Set([
  "p", "br", "div", "span", "b", "strong", "i", "em", "u", "ul", "ol", "li",
  "h1", "h2", "h3", "h4", "table", "thead", "tbody", "tr", "td", "th", "a",
]);
/** Tags whose content must never be shown as text. */
const DROPPED = new Set([
  "head", "title", "script", "style", "noscript", "template", "iframe", "object", "embed",
  "svg", "math", "form", "input", "button", "select", "textarea", "img", "video", "audio",
]);
const TAG_CLASS: Record<string, string> = {
  p: "my-2",
  ul: "my-2 list-disc pl-6",
  ol: "my-2 list-decimal pl-6",
  h1: "my-2 text-xl font-semibold",
  h2: "my-2 text-lg font-semibold",
  h3: "my-2 font-semibold",
  h4: "my-2 font-semibold",
  table: "my-2 border-collapse",
  td: "border border-line px-2 py-1 align-top",
  th: "border border-line px-2 py-1 text-left",
  b: "font-semibold",
  strong: "font-semibold",
};
/** Web addresses in plain text, as ingestion finds them; trailing punctuation is trimmed. */
const TEXT_URL_RE = /(?:https?:\/\/|www\.)[^\s<>"')\]]+/gi;
const TRAILING_PUNCTUATION_RE = /[.,;:!?]+$/;

export type LinkHandler = (url: string) => void;

export function SafeEmailBody({ html, text, onLink }: { html: string | null; text: string; onLink: LinkHandler }) {
  const content = useMemo(() => (html ? renderHtml(html, onLink) : renderText(text, onLink)), [html, text, onLink]);
  return <div className="text-[15px] leading-relaxed text-ink [overflow-wrap:anywhere]">{content}</div>;
}

function renderHtml(html: string, onLink: LinkHandler): ReactNode {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return Array.from(doc.body.childNodes).map((node, i) => renderNode(node, String(i), onLink));
}

function renderNode(node: Node, key: string, onLink: LinkHandler): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.nodeType !== Node.ELEMENT_NODE) return null; // comments, processing instructions
  const element = node as Element;
  const tag = element.tagName.toLowerCase();
  if (DROPPED.has(tag)) return null;
  if (tag === "a") {
    // A link shows its visible text only, so no block content ends up inside a button.
    const href = element.getAttribute("href")?.trim() ?? "";
    const label = (element.textContent ?? "").replace(/\s+/g, " ").trim();
    if (!href) return label;
    return <EmailLink key={key} url={href} onLink={onLink}>{label || href}</EmailLink>;
  }
  const children = Array.from(element.childNodes).map((child, i) => renderNode(child, `${key}.${i}`, onLink));
  if (tag === "br") return <br key={key} />;
  if (!ALLOWED.has(tag)) return <Fragment key={key}>{children}</Fragment>;
  return createElement(tag, { key, className: TAG_CLASS[tag] }, ...children);
}

/** Plain-text body: line breaks kept, web addresses made clickable. */
function renderText(text: string, onLink: LinkHandler): ReactNode {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TEXT_URL_RE)) {
    const found = match[0].replace(TRAILING_PUNCTUATION_RE, "");
    const start = match.index ?? 0;
    parts.push(text.slice(last, start));
    const url = found.toLowerCase().startsWith("www.") ? `http://${found}` : found;
    parts.push(<EmailLink key={start} url={url} onLink={onLink}>{found}</EmailLink>);
    last = start + found.length;
  }
  parts.push(text.slice(last));
  return <div className="whitespace-pre-wrap">{parts}</div>;
}

/** A link in an email. Hovering shows where it really goes, like a mail client's status bar. */
function EmailLink({ url, onLink, children }: { url: string; onLink: LinkHandler; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={() => onLink(url)}
      title={`Link goes to ${url}`}
      className="inline cursor-pointer rounded-sm text-left text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
    >
      {children}
    </button>
  );
}
