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

`helpers.py` implements the contract in `app/incidents/ai_hooks.py`:
`incident_summary(incident)`, `employee_notification(incident, employee_id)` and
`checklist_reason(incident_type, item_key, default)`. Each returns `""` when there is no
grounded LLM answer, so `ai_hooks` falls back to C's template. `checklist_reason` always
returns `""` on purpose: C's rationales are already plain and more precise. These calls
use the cache or the GPU server only (`allow_local=False`), never the slow laptop model.

## Regenerate the cache (when demo emails, detection wording or prompts change)

A cached answer is only used for the identical prompt, so after such changes the
demo silently falls back to templates until the cache is rebuilt (~1 min on GPU):

```bash
python -m app.llm.batch export                     # laptop -> cache/prompts.jsonl
python app/llm/generate_offline.py prompts.jsonl responses.jsonl   # GPU box
python -m app.llm.batch import responses.jsonl     # laptop -> cache/responses.json
```

Current cache: 192 answers (16 demo email explanations, 80 employee notifications,
96 incident summaries over C's 4 incident types).
