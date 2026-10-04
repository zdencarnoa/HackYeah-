/**
 * Live mode: replace the mock assessments with B's live ones. Every screen reads an
 * email's verdict from lib/mocks (EMAIL_BY_ID), so swapping it there once switches the
 * inbox, the risk cards and the admin lists to the backend's ML + rules + LLM text.
 * If the backend does not answer, the generated mocks stay in place.
 */

import { liveApi } from "../api";
import { EMAIL_BY_ID } from "../mocks";

let loading: Promise<number> | null = null;

/** Fetches once per page load; resolves to the number of verdicts replaced. */
export function loadLiveAssessments(): Promise<number> {
  loading ??= liveApi.assessments().then((result) => {
    if (!result.ok) return 0;
    let replaced = 0;
    for (const [id, assessment] of Object.entries(result.data)) {
      const email = EMAIL_BY_ID[id];
      if (email) {
        email.assessment = assessment;
        replaced += 1;
      }
    }
    return replaced;
  });
  return loading;
}
