# Person B: ML, risk fusion, LLM — guide for the team (and your Claude)

B turns an email into an **`Assessment`**: a risk level (LOW / MEDIUM / HIGH / CRITICAL),
the evidence behind it, a plain-language explanation and the next action. Everyone else
consumes that object; nobody needs to know how it is computed.

- Code: `backend/app/scoring/` (fusion, API), `backend/app/ml/` (classifier), `backend/app/llm/` (explanations)
- Tests: `backend/tests/scoring/`
- Branch: `risk_scoring`
- Status (2026-10-04): all B tasks from `Noina radionica.md` and B1–B3 from `INTEGRATION_PLAN.md` done;
  B4 waits on C2 (routers mounted in `main.py`).

## Where B fits

```
.eml ──► A: parse + detect() ──► Signal[] ─┐
                                           ├─► B: fusion ──► Assessment ──► C (MessageIn.risk), UI
email text ──► B: DistilBERT ──► ml signal ┘        │
                                                    └─► B: LLM / template explanation
```

## How to use it (copy these)

**Score one email** — always on the ORIGINAL message, before A's link rewriting:

```python
from app.scoring.analyze import analyze

assessment = analyze(message)                    # "Is this safe?" upload: may use a live LLM
assessment = analyze(message, live_llm=False)    # scan-on-delivery: never waits on a model
```

**Delivery glue (D1 / C3)** — score once per email, not once per recipient:

```python
a = analyze(message, live_llm=False)
for recipient in message.recipients:
    ingest_message(db, MessageIn(id=message.id, sender=message.sender, recipient=recipient,
                                 subject=message.subject, body=message.body_text,
                                 urls=[l.url for l in message.urls], risk=a.risk))
```

**Mount the HTTP route (C2)** in `main.py`:

```python
from app.scoring.router import router as scoring_router
app.include_router(scoring_router)   # POST /api/analyze (.eml upload), POST /api/analyze/message (JSON)
```

**Load the model at startup** (in the FastAPI lifespan), not on the first email:

```python
from app.scoring.ml_signal import warm_up
warm_up()   # "distilbert-v1", "tfidf-fallback" or None (rules only)
```

**Texts for C's incidents** (cached LLM text with a deterministic fallback):

```python
from app.llm.helpers import checklist_rationale, employee_notification, incident_summary
checklist_rationale("Revoke active sessions", "credential_phishing")           # keys of helpers.RATIONALE
employee_notification("Alice", "credential_phishing", ["email_scored", "link_clicked", "password_reuse"],
                      domain="micr0soft-verify.example")
incident_summary("credential_phishing", Severity.CRITICAL, evidence_kinds,
                 messages=14, recipients=7, departments=3, employee="Alice")
```

## The Assessment (in `app/schemas.py`)

| Field | Meaning | Show in UI |
|---|---|---|
| `risk` | `Severity` 0–3, set only by fusion rules | risk badge |
| `explanation.summary` / `.reasons` | plain language, strongest first | risk card |
| `recommended_action` | deterministic next step | risk card |
| `uncertainties` | what could not be checked ("We could not…") | risk card, muted |
| `signals`, `score`, `ml_confidence`, `ml_model` | technical evidence | "Advanced details" only |
| `explanation.source` | `llm` or `template` | optional badge |

## Rules (do not break them in your code either)

1. **The LLM never sets the risk and never writes instructions.** Risk = fusion rules; actions,
   notification steps and counts are deterministic. The LLM only rephrases evidence.
2. **The ML score alone never reaches HIGH.** HIGH needs a moderate rule-based signal from A.
3. **An email alone is at most HIGH.** CRITICAL comes from C's escalation (click + password, unusual sign-in).
4. **A missing check is an uncertainty, never evidence.**
5. **The demo needs no network:** LLM text for every demo email is cached in `app/llm/cache/`.

## Risk fusion in one table (`app/scoring/fusion.py`)

Points per signal category (strongest signal only): severity 1 → 1, 2 → 3, 3 → 6.
**LOW** < 3 ≤ **MEDIUM** < 6 ≤ **HIGH**. Floors to HIGH: credential request + impersonation,
known-bad indicator, MFA-code request, gift card + colleague impersonation, payment change +
mismatched sender. Demo results: 15 legit LOW, `amb-01` MEDIUM (+ DMARC uncertainty), 23 phishing HIGH.

## Setup on a new machine (from `backend/`)

```bash
pip install -r requirements.txt
pip install -r requirements-ml.txt     # optional: torch, transformers, scikit-learn, joblib
python -m app.ml.download_model        # optional: 255 MB weights from the model-v1 release (gh auth login)
```

Without the weights: TF-IDF fallback (capped to a weak signal, same demo verdicts).
Without the ML packages: rules only, with an uncertainty saying so. Both are tested.

## Where explanations come from (`app/llm/client.py`)

1. offline cache (`app/llm/cache/responses.json`, Qwen2.5-14B) → 2. GPU server via SSH tunnel
(`LLM_SERVER_URL`, ~5 s) → 3. Ollama `qwen2.5:3b` on the laptop (`LLM_LOCAL_URL`, ~25–40 s on CPU)
→ 4. templates. `LLM_LIVE=0` = cache + templates only. Details: `backend/app/llm/README.md`.

**When demo emails, A's evidence wording or the prompts change, the cache must be rebuilt**
(~1 min on the GPU box), otherwise those emails silently fall back to templates. Ask Person B.

## Model results (honest numbers for the pitch)

- Unseen source (CEAS_08, 33k emails): **95.8% accuracy, 97.6% recall, 5.9% false alarms**, AUC 0.992
- 39 demo emails: text model alone 36/39, full system 39/39
- Figures: `backend/app/ml/figures/` (regenerate: `python -m app.ml.figures`); details in `backend/app/ml/README.md`

## Testing

```bash
python -m pytest tests/scoring -q      # B's suite; never calls a live LLM (tests/scoring/conftest.py)
```

## Open items

- **B4** (needs C2): confirm `POST /api/analyze` is reachable on the live app.
- Rebuild the LLM cache after the last change to demo emails or detection wording, right before the demo.
