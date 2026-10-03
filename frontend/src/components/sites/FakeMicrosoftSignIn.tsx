"use client";

import { useState, type FormEvent } from "react";

import { DEMO_EMPLOYEE_ID } from "@/lib/mocks";

import { submitPasswordForm } from "./password";
import { PhishingReveal } from "./PhishingReveal";
import { SiteFrame } from "./SiteFrame";
import { mailboxHref, type SiteProps } from "./sites";

/**
 * The attacker's page in the demo: a generic enterprise sign-in card in the style of
 * a Microsoft 365 login (look and feel only; no real logo or artwork). Two steps like
 * the real thing: email, then password.
 */
export function FakeMicrosoftSignIn({ host, pageUrl, employeeId, employeeEmail }: SiteProps) {
  const [step, setStep] = useState<"email" | "password" | "revealed">("email");
  const [email, setEmail] = useState(employeeEmail);

  if (step === "revealed") {
    return <PhishingReveal host={host} mailbox={mailboxHref(employeeId, DEMO_EMPLOYEE_ID)} />;
  }

  function onEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (email.trim()) setStep("password");
  }

  function onPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitPasswordForm(event.currentTarget, employeeId, pageUrl) === "reported") setStep("revealed");
  }

  return (
    <SiteFrame pageUrl={pageUrl}>
      <main
        className="flex flex-1 items-center justify-center bg-[radial-gradient(circle_at_30%_20%,#e8eef5,#f2f2f2_60%)] px-4 py-16"
        style={{ fontFamily: '"Segoe UI", "Segoe UI Web", Tahoma, Arial, sans-serif' }}
      >
        <div className="w-full max-w-[440px] bg-white p-11 text-[#1b1b1b] shadow-[0_2px_6px_rgba(0,0,0,0.2)]">
          <Wordmark />

          {step === "email" ? (
            <form onSubmit={onEmail} className="mt-4">
              <h1 className="text-2xl font-semibold">Sign in</h1>
              <label htmlFor="fake-email" className="sr-only">
                Email, phone, or Skype
              </label>
              <input
                id="fake-email"
                name="email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Email, phone, or Skype"
                className="mt-4 w-full border-0 border-b border-[#666] px-0 py-1.5 text-[15px] outline-none focus:border-[#0067b8]"
              />
              <p className="mt-4 text-[13px]">
                No account? <span className="text-[#0067b8]">Create one!</span>
              </p>
              <p className="mt-2 text-[13px] text-[#0067b8]">Can&apos;t access your account?</p>
              <div className="mt-8 flex justify-end">
                <SubmitButton>Next</SubmitButton>
              </div>
            </form>
          ) : (
            <form onSubmit={onPassword} className="mt-4" autoComplete="off">
              <button
                type="button"
                onClick={() => setStep("email")}
                className="flex items-center gap-2 text-[15px] hover:underline"
                aria-label="Back to email"
              >
                <span aria-hidden>←</span>
                {email}
              </button>
              <h1 className="mt-3 text-2xl font-semibold">Enter password</h1>
              <label htmlFor="fake-password" className="sr-only">
                Password
              </label>
              <input
                id="fake-password"
                name="password"
                type="password"
                required
                autoComplete="off"
                autoFocus
                placeholder="Password"
                className="mt-4 w-full border-0 border-b border-[#666] px-0 py-1.5 text-[15px] outline-none focus:border-[#0067b8]"
              />
              <p className="mt-4 text-[13px] text-[#0067b8]">Forgot password?</p>
              <div className="mt-8 flex justify-end">
                <SubmitButton>Sign in</SubmitButton>
              </div>
            </form>
          )}
        </div>
      </main>
    </SiteFrame>
  );
}

function Wordmark() {
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden className="size-5 bg-[#8a8a8a]" />
      <span className="text-[17px] font-semibold text-[#5e5e5e]">Microsoft</span>
    </div>
  );
}

function SubmitButton({ children }: { children: string }) {
  return (
    <button
      type="submit"
      className="min-w-[108px] bg-[#0067b8] px-3 py-1.5 text-[15px] text-white hover:bg-[#005da6] focus-visible:outline-offset-2"
    >
      {children}
    </button>
  );
}
