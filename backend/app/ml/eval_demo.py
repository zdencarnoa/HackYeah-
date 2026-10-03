"""Score the team's demo emails (Person D's data/emails/*.json) with a trained model.

These emails are never used for training: they are the closest thing we have to
the real demo, so they are the honest final check.

Usage (from backend/):
    python -m app.ml.eval_demo                      # baseline TF-IDF model
    python -m app.ml.eval_demo --model transformer  # DistilBERT in app/ml/models/transformer_syn/
    python -m app.ml.eval_demo --model transformer --path some/other/model_dir
"""
import json
import subprocess
import sys
from pathlib import Path

from app.ml.text import email_text, normalize

ROOT = Path(__file__).resolve().parents[3]  # repo root
MODEL_PATH = Path(__file__).resolve().parent / "models" / "baseline.joblib"

DEMO_FILES = ["legitimate", "campaign_microsoft", "phishing_misc"]
# Demo data lives on Person D's branch until it is merged into main.
FALLBACK_REF = "origin/simulation"


def load_demo_emails() -> list[dict]:
    emails = []
    for name in DEMO_FILES:
        path = ROOT / "data" / "emails" / f"{name}.json"
        if path.exists():
            raw = path.read_text(encoding="utf-8")
        else:
            raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{FALLBACK_REF}:data/emails/{name}.json"],
                                 capture_output=True, text=True, encoding="utf-8", check=True).stdout
        data = json.loads(raw)
        emails.extend(data if isinstance(data, list) else data["emails"])
    return emails


def baseline_scorer():
    import joblib
    pipeline = joblib.load(MODEL_PATH)["pipeline"]
    return lambda texts: pipeline.predict_proba([normalize(t) for t in texts])[:, 1]


def transformer_scorer(path: str | None):
    from app.ml.transformer_model import PhishingTransformer
    model = PhishingTransformer.load(Path(path)) if path else PhishingTransformer.load()
    return model.predict_proba


def main() -> None:
    kind = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "baseline"
    path = sys.argv[sys.argv.index("--path") + 1] if "--path" in sys.argv else None
    score = transformer_scorer(path) if kind == "transformer" else baseline_scorer()
    emails = load_demo_emails()
    probs = score([email_text(e["subject"], e["body_text"]) for e in emails])

    correct = {"phishing": [0, 0], "legitimate": [0, 0]}
    for e, p in sorted(zip(emails, probs), key=lambda x: (x[0]["scenario"]["label"], -x[1])):
        label = e["scenario"]["label"]
        ok = (p >= 0.5) == (label == "phishing")
        correct[label][0] += ok
        correct[label][1] += 1
        print(f"{'OK' if ok else 'XX'} {p * 100:5.1f}%  [{label[:5]}] {e['subject'][:70]}")

    total = sum(c for c, _ in correct.values()), sum(n for _, n in correct.values())
    print(f"\n{kind}: phishing caught {correct['phishing'][0]}/{correct['phishing'][1]}, "
          f"legit recognised {correct['legitimate'][0]}/{correct['legitimate'][1]}, "
          f"overall {total[0]}/{total[1]} ({total[0] / total[1]:.0%})")


if __name__ == "__main__":
    main()
