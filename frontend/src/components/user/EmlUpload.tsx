"use client";

/**
 * "Is this safe?" for an email outside the inbox: drop or pick an .eml file, or paste
 * the email's source (Gmail "Show original", Outlook "View source"), and get the same
 * risk card. Mock mode can check the demo emails only (see lib/api.ts).
 */

import { useState, type DragEvent } from "react";

import { analyzeEmlFile, type AnalyzeResult } from "@/lib/api";
import { RiskCard } from "./RiskCard";

type Status = { kind: "idle" } | { kind: "checking"; name: string } | { kind: "done"; name: string; result: AnalyzeResult };

export function EmlUpload() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const [pasted, setPasted] = useState("");

  async function check(file: File | undefined) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".eml")) {
      setStatus({
        kind: "done",
        name: file.name,
        result: { ok: false, error: "Only .eml files can be checked. In your mail app, save or download the email as a file first." },
      });
      return;
    }
    setStatus({ kind: "checking", name: file.name });
    setStatus({ kind: "done", name: file.name, result: await analyzeEmlFile(file) });
  }

  function checkPasted() {
    if (!pasted.trim()) return;
    // The source of an email is an .eml file in text form.
    void check(new File([pasted], "pasted-email.eml", { type: "message/rfc822" }));
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void check(event.dataTransfer.files[0]);
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Check an email</h2>
        <p className="mt-1 text-sm text-muted">
          Not sure about an email? Drop its .eml file here or paste its source. Security Copilot checks it without opening links or attachments.
        </p>
      </div>

      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center focus-within:ring-2 focus-within:ring-accent ${
          dragging ? "border-accent bg-accent/10" : "border-line bg-panel hover:bg-panel-2"
        }`}
      >
        <span aria-hidden className="text-3xl">✉</span>
        <span className="text-sm font-medium text-ink">Drop an .eml file here, or click to choose one</span>
        <span className="text-xs text-muted">Only .eml files</span>
        <input
          type="file"
          accept=".eml,message/rfc822"
          className="sr-only"
          onChange={(e) => {
            void check(e.target.files?.[0]);
            e.target.value = ""; // the same file can be checked again
          }}
        />
      </label>

      <div className="space-y-2">
        <label htmlFor="pasted-email" className="block text-sm font-medium text-ink">
          Or paste the email source
        </label>
        <p className="text-xs text-muted">
          Gmail: ⋮ → Show original → Copy to clipboard. Outlook: File → Properties, or View → View message source.
        </p>
        <textarea
          id="pasted-email"
          value={pasted}
          onChange={(e) => setPasted(e.target.value)}
          rows={6}
          spellCheck={false}
          placeholder={"From: …\nTo: …\nSubject: …\n\n…"}
          className="w-full resize-y rounded-lg border border-line bg-panel px-3 py-2 font-mono text-xs text-ink placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <button
          type="button"
          onClick={checkPasted}
          disabled={!pasted.trim() || status.kind === "checking"}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink disabled:opacity-40"
        >
          Check pasted email
        </button>
      </div>

      <div aria-live="polite">
        {status.kind === "checking" && <p className="text-sm text-muted">Checking {status.name}…</p>}
        {status.kind === "done" && !status.result.ok && (
          <p className="rounded-lg border border-medium/40 bg-medium/10 px-4 py-3 text-sm text-ink">
            <span className="font-semibold">{status.name}:</span> {status.result.error}
          </p>
        )}
        {status.kind === "done" && status.result.ok && (
          <div className="space-y-2">
            <p className="text-sm text-muted">
              Result for <span className="font-medium text-ink">{status.name}</span>
              {status.result.message && <> — “{status.result.message.subject}”</>}
            </p>
            <RiskCard assessment={status.result.assessment} message={status.result.message} />
          </div>
        )}
      </div>
    </div>
  );
}
