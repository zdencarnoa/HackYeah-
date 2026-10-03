# LLM layer (Person B)

The LLM only **explains**. It never sets the risk level, never writes instructions
(recommended actions and notification steps are deterministic) and never sees the
raw email, only evidence that is already in an Assessment. Every answer is
grounding-checked (no domain, URL or number that is not in the evidence); a failed
answer falls back to a template, so the demo always has text.

Where answers come from, in order:

1. **Offline cache** `cache/responses.json`: generated before the demo by
   Qwen2.5-14B-Instruct (Apache-2.0) on a GPU box. No network or GPU needed in the demo.
2. **Live model** (optional): any OpenAI-compatible endpoint, e.g. Ollama on the
   presenting laptop: `LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=qwen2.5:3b`.
3. **Templates** (`app/scoring/templates.py`, `helpers.py`).

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
