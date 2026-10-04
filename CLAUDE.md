# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a HackYeah hackathon project. Remote: https://github.com/zdencarnoa/HackYeah- (`main` plus one branch per area). The `backend/app/*` folders are empty placeholders so far. `idea.md` is the full product spec for **Security Copilot**: a phishing-detection and incident-response assistant for small and medium-sized organizations that have no security team. Read `idea.md` before making design decisions. It is the source of truth for scope, UX, and the demo script.

Python 3.12 venv at the repo root (`.venv`). From `backend/`:
- Install: `..\.venv\Scripts\python -m pip install -r requirements.txt`
- All tests: `..\.venv\Scripts\python -m pytest -q`
- One test: `..\.venv\Scripts\python -m pytest tests/test_seed.py::test_demo_campaign_matches_the_script`
- On macOS/Linux use `../.venv/bin/python` instead, e.g. `../.venv/bin/python -m pytest tests/detection -q`

Demo data lives in `data/` (`org.json`, `approved_logins.json`, `emails/*.json`) and is loaded and validated by `app/simulation/seed.py`.

Every message enters detection as an `.eml`: `app.detection.parse_eml` parses uploads, and `message_from_sim` renders a `SimEmail` to `.eml` and parses it the same way. `python -m app.detection.export_eml` writes the demo mail to `data/eml/` (gitignored) for the "Is this safe?" upload.

Detection integration:
- On delivery, in this order: `message_from_sim(sim)`, then `detect(message)` on the original, then `rewrite_links(message, employee_id)` for each inbox copy. Never run `detect()` on a rewritten copy.
- `app.detection.router.router` holds `POST /api/analyze/signals`, `GET /r/{token}` and a placeholder `/demo/{host}/{path}` page. C mounts it with `app.include_router(router)`.
- A click emits a `SimEvent(type=link_clicked)` before redirecting, and only `.example`/`.test` domains are ever forwarded. Tokens are in memory and clicks are only logged until C calls `app.detection.rewrite.configure(store=..., on_click=...)`. D's reset calls `clear_links()`.
- Env: `DETECTION_BASE_URL` (default `http://localhost:8000`) and `DEMO_SITE_URL` (default `<base>/demo`, where D's fake site goes).

Scoring integration (Person B, full guide: `docs/PERSON_B.md`):
- `app.scoring.analyze.analyze(message)` returns the shared `Assessment` (risk, explanation, recommended action, uncertainties). It runs `detect()` itself, so call it on the ORIGINAL message, once per email, before link rewriting. On delivery use `analyze(message, live_llm=False)` so it never waits on a model; put `assessment.risk` into C's `MessageIn.risk`.
- `app.scoring.router.router` holds `POST /api/analyze` (.eml upload) and `POST /api/analyze/message` (JSON `Message`). C mounts it with `app.include_router(router)`. Call `app.scoring.ml_signal.warm_up()` in the app lifespan.
- Text for C's incidents: `app.llm.helpers` (`checklist_rationale`, `employee_notification`, `incident_summary`).
- Never compute or override risk elsewhere, and never let an LLM set it. Optional ML setup: `pip install -r requirements-ml.txt` and `python -m app.ml.download_model`; without it scoring falls back to TF-IDF or rules only.
- Explanations for demo emails are cached in `app/llm/cache/`. After changing demo emails or detection wording, ask B to rebuild the cache, or those emails fall back to template text.

## Intended stack (from idea.md §16, not yet chosen for certain)

- Frontend: Next.js + React + TypeScript + Tailwind; React Flow, D3, or Cytoscape for the dependency graph
- Backend: Python + FastAPI
- DB: SQLite for the prototype (PostgreSQL is optional)
- ML: scikit-learn, sentence-transformers, or Hugging Face models, plus an LLM API

## Architecture (planned)

The pipeline is: message → ingestion → three parallel analyzers (**ML classifier**, **URL/domain analysis**, **rule engine**) → **risk assessment** (LOW / MEDIUM / HIGH / CRITICAL) → **LLM explanation layer** → two UIs (**Employee Copilot** and **Admin Dashboard**) → **incident management** → **response/recovery**.

Cross-cutting concepts that span several components:
- **Campaign correlation**: group related messages by sender infrastructure, similar subject or content, the same destination URL, and delivery time. Incidents and the dashboard are organized around campaigns, not single emails.
- **Employee decision flow**: after analysis, the user reports what happened (no interaction / clicked / downloaded / entered password / entered other info). An answer of "entered password" escalates to incident response and creates an admin-facing incident.
- **Blast radius**: a *simulated* organizational graph (employee → identity provider → email / file storage / internal apps) that shows what a compromised account could reach.
- **Containment and recovery**: quarantine, block sender or domain, notify, revoke sessions, reset credentials, plus a recovery-progress view.

## Ownership

There are four human developers and Claude. **Claude owns all UI in `frontend/`** and builds against mocks that follow the shared contracts in `backend/app/schemas.py`. Only change that file in coordination with the team. Backend ownership:
- A: `backend/app/detection/` (parsing, rules, URL and domain checks)
- B: `scoring/`, `ml/`, `llm/` (risk fusion and grounded explanations)
- C: `incidents/`, `campaigns/`, `db/`, `api/` (decision flow, correlation, SSE events)
- D: `simulation/`, `data/` (synthetic org, blast radius, containment, recovery, attack engine, reset)

Demo attacker infrastructure uses reserved `.example` and `.test` domains only.

## Detection model (decided)

- Detection must not depend on the employee. Every delivered email is scored on arrival. Clicks are recorded by rewriting links to `/r/{token}`. A password typed on any domain outside the `ApprovedLogins` list fires a simulated Chrome `PASSWORD_REUSE_EVENT`. A simulated unusual sign-in follows. Employee reports are backup evidence only.
- Severity escalates with evidence. The system recommends containment, and the admin approves it.
- The ML model is trained on the Kaggle Phishing Email Dataset (naserabdullahalam/phishing-email-dataset, about 82.5k emails from 6 merged corpora). Keep it out of git under `data/raw/`. Watch for the model learning which source corpus an email came from instead of phishing itself. The ML score never sets HIGH or above on its own.

## Non-negotiable design rules

- **The LLM never decides alone whether a message is malicious.** The risk verdict combines deterministic rules, ML output, and threat indicators. The LLM explains, summarizes, and recommends.
- **Explain with evidence, not scores.** Show human-readable reasons first. Put ML confidence and raw technical data (SPF, DMARC, entropy) under "Advanced details".
- **State uncertainty and never invent evidence.** Use wording like "We could not verify…" or "This does not prove…". Recommendations are guidance, not claims about what actually happened.
- **Every result ends with a next action** for the user.
- **All containment actions are simulated** and must be clearly labeled as such in the UI (for example, "✓ SIMULATION — 7 messages would be quarantined"). Never build anything that touches real accounts, mailboxes, or infrastructure. Never execute attachments.
- **Use synthetic or public data only.** The demo dataset needs both legitimate and phishing messages, with several variants of one campaign so correlation can be shown.

## Priorities

Work in this order: a working end-to-end demo first, then UX polish, credible detection, clear explanations, the incident-response workflow, campaign correlation, the dependency visualization, and extra AI features last. A small flawless flow from detection to recovery beats many unfinished features.

The demo scenario is in `idea.md` §18–23: a fake "Microsoft Security" email from `micr0soft-example.test` (idea.md says `.com`; changed to stay on reserved TLDs), Alice enters her password, the admin gets an alert, discovers a campaign of 14 messages and 7 recipients, views the blast radius, contains the campaign, and tracks recovery. Build features so this scenario runs smoothly.
