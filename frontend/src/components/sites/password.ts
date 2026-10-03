/**
 * The one place a typed password is touched. Imported only by client components.
 */

import { demoActions } from "@/lib/demo/store";

export type PasswordResult = "empty" | "approved" | "reported";

/**
 * Reads only whether something was typed in the form's password field, then clears
 * the form at once. The password itself is never stored, logged, put in state or
 * sent anywhere: only the fact that one was entered, on which address, is reported
 * (a simulated Chrome PASSWORD_REUSE_EVENT; approved company addresses never fire).
 */
export function submitPasswordForm(form: HTMLFormElement, employeeId: string, pageUrl: string): PasswordResult {
  const field = form.elements.namedItem("password");
  const typed = field instanceof HTMLInputElement && field.value.length > 0;
  form.reset();
  if (!typed) return "empty";
  return demoActions.recordPasswordEntry(employeeId, pageUrl);
}
