"use client";

/** Live attack status for the demo bar: polls D's GET /api/sim/attack/status. */

import { useCallback, useEffect, useState } from "react";

import { LIVE, liveApi } from "../api";
import type { AttackStatus } from "../contracts";

export interface LiveAttack {
  status: AttackStatus | null;
  /** Set when the last poll or action failed; cleared on the next success. */
  error: string | null;
  /** Replace the status with a response from an action, so the bar updates at once. */
  show: (status: AttackStatus | null, error?: string | null) => void;
}

export function useLiveAttack(intervalMs = 1000): LiveAttack {
  const [status, setStatus] = useState<AttackStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const show = useCallback((next: AttackStatus | null, message: string | null = null) => {
    if (next) setStatus(next);
    setError(message);
  }, []);

  useEffect(() => {
    if (!LIVE) return;
    let cancelled = false;
    async function poll() {
      const result = await liveApi.attackStatus();
      if (cancelled) return;
      if (result.ok) show(result.data);
      else setError(result.error);
    }
    void poll();
    const timer = window.setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [intervalMs, show]);

  return { status, error, show };
}
