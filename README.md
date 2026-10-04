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

## Models

### Phishing classifier (DistilBERT)

The ML signal is a fine-tuned **DistilBERT** (`DistilBertForSequenceClassification`, 6 layers,
~255 MB). The weights are too big for git, so they are published as the `model.safetensors` asset
of the GitHub release/tag **`model-v1`**. Fetch them once per machine:

```bash
cd backend && ../.venv/bin/python -m app.ml.download_model
```

The repo is private, so this needs the GitHub CLI (`gh auth login`) or a `GITHUB_TOKEN`; the
download is checked against its SHA-256. Without the weights scoring falls back to TF-IDF/rules and
reports the missing model as an uncertainty. The ML score never sets HIGH or above on its own.

### Explanation LLM (Qwen)

The LLM is **not in the repo**: it is far too large for GitHub. It only writes explanations,
summaries and recommendations; it never decides risk. Three tiers, tried in order:

1. **GPU server**: Qwen2.5 with **14B parameters** on our GPU server (`app/llm/serve_openai.py`,
   reached through an SSH tunnel on `localhost:8001`), ~5 s per answer.
2. **Local backup**: Qwen2.5 **3B** (`qwen2.5:3b`) running in the **Ollama** app on the laptop
   (`ollama pull qwen2.5:3b`), ~30-60 s on CPU.
3. **Templates**: if neither model is reachable, the built-in template explanations are used,
   so the demo always works.

Explanations for the demo emails are pre-generated and cached in `backend/app/llm/cache/`, so they
never wait on a model. `LLM_LIVE=0` turns the live tiers off. Overrides: `LLM_SERVER_URL`,
`LLM_LOCAL_URL`, `LLM_LOCAL_MODEL`. Details: `backend/app/llm/README.md` and `docs/PERSON_B.md`.

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
