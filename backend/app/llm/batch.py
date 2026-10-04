"""Build the offline LLM cache for the demo (so the demo needs no network or GPU).

1. laptop:  python -m app.llm.batch export    -> app/llm/cache/prompts.jsonl
2. GPU box: python generate_offline.py prompts.jsonl responses.jsonl   (open-source model)
3. laptop:  python -m app.llm.batch import responses.jsonl  -> app/llm/cache/responses.json

Prompts are the exact ones the live path sends, keyed by fingerprint, so a cached
answer is used only for an identical question. Answers are still grounding-checked
at use time; a rejected one falls back to the template.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from app.incidents.checklist_templates import TEMPLATES  # C's incident types and checklist steps
from app.llm.client import CACHE_FILE, parse_json
from app.llm.explain import llm_inputs
from app.llm.prompts import explanation_messages, fingerprint, notification_messages, summary_messages

PROMPTS_FILE = CACHE_FILE.parent / "prompts.jsonl"
INCIDENT_TYPES = list(TEMPLATES)
ESCALATION = ["email_scored", "link_clicked", "password_reuse", "unusual_signin", "user_report"]


def _demo_explanations():
    from app.detection import message_from_sim
    from app.scoring.analyze import analyze
    from app.simulation.seed import load_emails
    for sim in load_emails():
        for use_ml in (True, False):  # cover laptops with and without the ML model
            a = analyze(message_from_sim(sim), use_ml=use_ml)
            evidence, unsure = llm_inputs(a.risk, a.signals, a.uncertainties)
            yield "explanation", explanation_messages(int(a.risk), evidence, unsure)


def _escalation_sets():
    """Evidence kinds as they accumulate during an incident, with and without a user report."""
    for i in range(1, len(ESCALATION)):
        base = ESCALATION[:i]
        yield sorted(base)
        yield sorted(base + ["user_report"])


def _demo_domains():
    from app.simulation.seed import load_emails
    hosts = {urlsplit(u).hostname for e in load_emails() if e.scenario.label == "phishing" for u in e.urls}
    return sorted(h for h in hosts if h) + [None]


def collect() -> dict[str, tuple[str, list[dict]]]:
    prompts: dict[str, tuple[str, list[dict]]] = {}

    def add(kind, messages):
        prompts.setdefault(fingerprint(messages), (kind, messages))

    for kind, messages in _demo_explanations():
        add(kind, messages)
    for itype in INCIDENT_TYPES:
        for kinds in {tuple(k) for k in _escalation_sets()}:
            for severity in (1, 2, 3):
                add("summary", summary_messages(itype, severity, list(kinds)))
            for domain in _demo_domains() if itype == "credential_phishing" else [None]:
                add("notification", notification_messages(itype, list(kinds), domain))
    return prompts


def export() -> None:
    prompts = collect()
    PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROMPTS_FILE.open("w", encoding="utf-8") as f:
        for fp, (kind, messages) in prompts.items():
            f.write(json.dumps({"fingerprint": fp, "kind": kind, "messages": messages}) + "\n")
    counts = {k: sum(1 for kind, _ in prompts.values() if kind == k) for k in {k for k, _ in prompts.values()}}
    print(f"wrote {len(prompts)} prompts to {PROMPTS_FILE}: {counts}")


def import_responses(path: Path) -> None:
    cache, bad = {}, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        answer = parse_json(row["text"])
        if answer is None:
            bad += 1
            continue
        cache[row["fingerprint"]] = answer
    CACHE_FILE.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"cached {len(cache)} answers ({bad} unparseable) in {CACHE_FILE}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        export()
    elif sys.argv[1:2] == ["import"]:
        import_responses(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)
