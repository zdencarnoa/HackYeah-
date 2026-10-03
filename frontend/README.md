# Security Copilot frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4 + React Flow. All screens of the demo:

| Route | Who | What |
|---|---|---|
| `/` | everyone | Start page with links to both personas |
| `/user` | employee (Alice by default, `?as=e03` for others) | Mailbox: warning banners, "Is this safe?", risk card, "What happened?" flow, `.eml` check |
| `/admin` | administrator | List of warning and dangerous emails, live alerts, campaign, incident, blast radius, containment, recovery, demo bar (press `D`) |
| `/demo/{host}/{path}` | employee | Simulated pages behind links: the fake Microsoft sign-in, the company sign-in, placeholders |

## Run

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

For the demo, open `/user` and `/admin` side by side in two windows of the same browser, then press `D` on the admin page and launch the attack. Before a demo, press Reset.

Checks: `npx tsc --noEmit`, `npx eslint src`, `npm run build`.

## Mock mode and live mode

Without configuration the UI runs on **mocks** and needs no backend:

- `src/mocks/*.json` is generated from the real backend by `scripts/generate_mocks.py`: D's demo mail and org, run through A's detection and B's `analyze()`. Regenerate it from a checkout where A's, B's and D's work is merged:

  ```bash
  PYTHONPATH=<checkout>/backend python frontend/scripts/generate_mocks.py <checkout>
  ```

- `src/lib/demo/` simulates what C's and D's APIs will do: delivery of the attack waves, clicks, password-reuse events, incidents, containment and recovery. Its state is saved in `localStorage` and shared between windows with a `BroadcastChannel`, so the employee and admin windows tell the same story.

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local` to use the live backend. `src/lib/api.ts` is the only file that talks to it; each mock in `lib/demo/selectors.ts` returns the same contract shape as the endpoint that replaces it.

## Layout

```
src/lib/contracts.ts        TypeScript mirror of backend/app/schemas.py and the B/C proposals
src/lib/mocks.ts            typed access to src/mocks/*.json
src/lib/demo/               mock demo engine: state.ts (event log), selectors.ts (views), store.ts (sync + actions)
src/lib/api.ts              backend calls; mock fallbacks
src/components/ui/          shared pieces: RiskBadge, SimulationBadge, ClientOnly, formatting
src/components/user/        employee mailbox
src/components/admin/       admin console; sections/ holds the detail tabs
src/components/sites/       simulated sign-in pages
```

## Rules the UI follows

- Plain language first; signals, ML confidence and headers only under "Advanced details".
- Every result ends with a next action.
- Every containment result is labeled SIMULATION. Nothing touches real accounts or mailboxes.
- Email HTML is attacker-controlled: it is rendered through an allowlist, never with `dangerouslySetInnerHTML`.
- The simulated sign-in pages never store or send what is typed.
