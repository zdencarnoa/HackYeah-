# Security Copilot

Built at HackYeah (Kraków). A phishing-detection and incident-response assistant for small and
medium-sized organizations that have no security team.

> Don't just detect the attack. Help people understand it, decide what to do, contain it, and recover.

```
message → detection → risk score → explanation → employee decision
        → incident → campaign correlation → blast radius → containment → recovery
```

The full product spec and demo script are in [`idea.md`](idea.md). Everything runs on synthetic
data, and every containment action is **simulated**: nothing touches real accounts or mailboxes.
Attacker infrastructure uses reserved `.example` / `.test` domains only.

## What it does

- **Employee Copilot**: every delivered email is scored on arrival. The user sees plain-language
  reasons first, uncertainty stated honestly, and a next action. ML confidence and raw
  SPF/DMARC data sit under "Advanced details". An "Is this safe?" upload accepts `.eml` files.
- **Admin Dashboard**: live incidents over SSE, campaign correlation (e.g. 14 messages / 7 recipients),
  blast radius graph, simulated containment, and a recovery tracker.
- **Risk is deterministic**: rules + ML + threat indicators decide LOW / MEDIUM / HIGH / CRITICAL.
  The LLM only explains, summarizes and recommends; it never sets risk.

## Repository layout

| Path | Contents |
|---|---|
| `backend/app/detection/` | `.eml` parsing, rules, URL/domain analysis, link rewriting |
| `backend/app/scoring/`, `ml/`, `llm/` | risk fusion, DistilBERT classifier, grounded explanations |
| `backend/app/incidents/`, `campaigns/`, `db/`, `api/` | decision flow, correlation, SQLite, SSE |
| `backend/app/simulation/` | synthetic org, attack engine, blast radius, containment, recovery |
| `backend/app/schemas.py` | shared contracts (change only in coordination) |
| `frontend/` | Next.js + React + TypeScript + Tailwind UI, React Flow graph |
| `data/` | demo org, approved logins, demo emails |
| `scripts/ui_demo_test.py` | end-to-end demo check through the real UI |
| `docs/PERSON_B.md` | scoring / ML / LLM details |

## Quick start

### Windows: one click

Double-click **`start_demo.bat`**. It opens a tunnel to the GPU server's LLM (if reachable), starts
the backend (:8000) and frontend (:3000) in live mode, resets the demo and opens Alice's mailbox
and the admin console (press **D** there for demo controls). **`stop_demo.bat`** stops everything.

### Manual (macOS / Linux / Windows)

Requires Python 3.12 and Node 20+.

```bash
# backend
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt     # Windows: .venv\Scripts\python
# optional ML classifier; without it scoring falls back to TF-IDF/rules
.venv/bin/python -m pip install -r backend/requirements-ml.txt
(cd backend && ../.venv/bin/python -m app.ml.download_model)
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local     # omit for mock mode
npm run dev                                                    # http://localhost:3000
```

Without `NEXT_PUBLIC_API_URL` the UI runs against mocks that follow the shared contracts.

## Tests

```bash
cd backend
../.venv/bin/python -m pytest -q                      # all (Windows: ..\.venv\Scripts\python)
../.venv/bin/python -m pytest tests/detection -q      # one area
```

Check the whole demo through the real UI before presenting (headless Chromium, ~1 min):

```bash
pip install playwright && python -m playwright install chromium   # once
python scripts/ui_demo_test.py
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | unset (mock mode) | backend URL for the frontend (live mode) |
| `DATABASE_URL` | SQLite file | backend database |
| `DETECTION_BASE_URL` | `http://localhost:8000` | base for rewritten links |
| `DEMO_SITE_URL` | `<base>/demo` | where the fake sign-in site lives |

## LLM text

Explanations for new emails come from the GPU server's Qwen 14B (~5 s), else Ollama's
`qwen2.5:3b` on the laptop (~30-60 s), else templates. Demo emails use cached LLM text
(`backend/app/llm/cache/`), so the demo never depends on the network.

## Demo scenario

A fake "Microsoft Security" email from `micr0soft-example.test` → Alice enters her password →
the admin gets a CRITICAL alert → campaign of 14 messages / 7 recipients → blast radius →
simulated containment → recovery progress.

## Data

The ML model is trained on the public Kaggle Phishing Email Dataset
(`naserabdullahalam/phishing-email-dataset`); raw data stays out of git under `data/raw/`.
Demo data is synthetic.

## License

See [`LICENSE`](LICENSE).
