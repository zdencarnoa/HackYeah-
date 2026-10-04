# LLM layer (Person B)

The LLM only **explains**. It never sets the risk level, never writes instructions
(recommended actions and notification steps are deterministic) and never sees the
raw email, only evidence that is already in an Assessment. Every answer is
grounding-checked (no domain, URL or number that is not in the evidence); a failed
answer falls back to a template, so the demo always has text.

Where answers come from, in order (`client.py`):

| # | Source | Speed | Needs |
|---|---|---|---|
| 1 | **Offline cache** `cache/responses.json` (Qwen2.5-14B-Instruct, Apache-2.0) | instant | nothing |
| 2 | **GPU server**: Qwen2.5-14B via `serve_openai.py` + SSH tunnel | ~5 s | server on + tunnel |
| 3 | **Laptop**: Ollama `qwen2.5:3b` (1.9 GB) | ~25-40 s on a laptop CPU | Ollama running |
| 4 | **Templates** (`app/scoring/templates.py`, `helpers.py`) | instant | nothing |

A source that is not running refuses the connection at once, so a missing tunnel or
Ollama costs nothing. `LLM_LIVE=0` turns 2 and 3 off. Overrides: `LLM_SERVER_URL`,
`LLM_LOCAL_URL`, `LLM_LOCAL_MODEL`, `LLM_SERVER_TIMEOUT`, `LLM_LOCAL_TIMEOUT`.

**GPU server (2):** on the box, in `~/hackyeah/work`:
`HF_HOME=~/hackyeah/hf nohup ../.venv/bin/python serve_openai.py --port 8001 &`
(~30 GB GPU memory, listens on 127.0.0.1 only). On the laptop: `ssh -N -L 8001:localhost:8001 lambda-gpu`.
Stop: `pkill -f serve_openai.py` on the box.

**Laptop (3):** install [Ollama](https://ollama.com), then `ollama pull qwen2.5:3b`.

## For Person C

```python
from app.llm.helpers import checklist_rationale, employee_notification, incident_summary

checklist_rationale("Revoke active sessions", "credential_phishing")
employee_notification("Alice", "credential_phishing", ["email_scored", "link_clicked", "password_reuse"],
                      domain="login.micr0soft-example.test")
incident_summary("credential_phishing", Severity.CRITICAL, evidence_kinds,
                 messages=14, recipients=7, departments=3, employee="Alice")
```

Checklist actions with a prepared rationale are the keys of `helpers.RATIONALE`.

## Regenerate the cache (when demo emails, detection wording or prompts change)

A cached answer is only used for the identical prompt, so after such changes the
demo silently falls back to templates until the cache is rebuilt (~1 min on GPU):

```bash
python -m app.llm.batch export                     # laptop -> cache/prompts.jsonl
python app/llm/generate_offline.py prompts.jsonl responses.jsonl   # GPU box
python -m app.llm.batch import responses.jsonl     # laptop -> cache/responses.json
```

Current cache: 195 answers (12 demo email explanations, 72 notifications,
72 incident summaries, 39 checklist rationales); 194/195 pass the grounding check.
