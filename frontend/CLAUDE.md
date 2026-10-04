@AGENTS.md

## This frontend

See README.md for routes, mock vs live mode and layout. Before changing code: contracts live in `src/lib/contracts.ts` (mirror of `backend/app/schemas.py`); screens read demo data only through `src/lib/demo/selectors.ts` and `src/lib/demo/store.ts`; use the semantic color tokens from `src/app/globals.css` (`bg-panel`, `text-muted`, `text-critical`, ...), never raw colors. Checks: `npx tsc --noEmit && npx eslint src && npm run build`.
