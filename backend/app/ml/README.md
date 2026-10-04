# ML phishing classifier (Person B)

Gives a **calibrated phishing probability** for an email's subject + body. It is one
input to risk fusion and never sets HIGH or above on its own. Sender, headers and
URLs are Person A's deterministic signals, not model features.

## Models

| File | What | Load | Used for |
|---|---|---|---|
| `models/transformer_syn/` | DistilBERT fine-tuned on Kaggle + synthetic modern emails, temperature-calibrated | ~1 s, CPU | main model |
| `models/baseline.joblib` | TF-IDF (hashed words + chars) + logistic regression | 0.2 s | fallback |

`models/transformer_syn/model.safetensors` (255 MB) is not in git (over GitHub's
100 MB limit). It is attached to the [`model-v1` release](https://github.com/zdencarnoa/HackYeah-/releases/tag/model-v1);
the other files in that folder are committed. **Setup, once per machine (from `backend/`):**

```bash
pip install -r requirements-ml.txt       # torch, transformers, scikit-learn, joblib
python -m app.ml.download_model          # needs `gh auth login` or GITHUB_TOKEN; SHA-256 checked
```

Without the weights the TF-IDF fallback runs; it is capped to a weak signal, so the
demo verdicts are the same (tested). Without the ML packages, scoring runs on rules
alone and states the missing model as an uncertainty.

```python
from app.ml.transformer_model import PhishingTransformer
from app.ml.text import email_text

model = PhishingTransformer.load()          # once at startup
p = model.predict_proba([email_text(subject, body)])[0]   # 0.0–1.0
```

## Results

| Test | TF-IDF + LR | DistilBERT + synthetic |
|---|---|---|
| Random split (optimistic) | 99.2% acc | – |
| Unseen source CEAS_08 (honest) | 93.0% acc, AUC 0.978 | 95.8-96.0% acc (two runs), AUC 0.992, recall 97.6% |
| Unseen source SpamAssassin | 92.8% acc, AUC 0.980 | – |
| Team demo emails (33) | 26/33 | 31/33 (all 12 legit LOW) |
| Calibration error (ECE, CEAS_08) | – | 3.3% → 2.0% (T = 1.99) |

Full outputs are in `logs/`. Caveat: the synthetic categories were chosen after
seeing which demo emails failed (texts were not copied), so the demo score is
somewhat optimistic; the unseen-source numbers are the honest ones.

The two demo phishing emails the model misses ("MFA re-enrolment", "Bob shared
Salary adjustments") are caught by Person A's sender signals; that is what fusion is for.

## Data pitfalls we handled

- **Source leakage:** each Kaggle corpus has its own era and style (dates alone reveal
  the label), so dates/headers are never features and evaluation holds out a whole source.
- **Duplicates:** 7,618 duplicate emails removed before splitting.
- **Domain gap:** the corpora are 2000s conversations, so modern automated notifications
  looked like spam. `synth_emails.py` adds 3,520 modern emails, both classes from the
  same categories, so the model learns content rather than "notification = phishing".
- Label 1 in the dataset means "phishing **or spam**".

## Reproduce (from `backend/`)

```bash
# dataset (gitignored) -> ../data/raw/
curl -L -o ../data/raw/ds.zip https://www.kaggle.com/api/v1/datasets/download/naserabdullahalam/phishing-email-dataset
python -m app.ml.synth_emails                          # ../data/synthetic/modern_emails.csv
python -m app.ml.train_baseline                        # TF-IDF baseline + evaluation (~20 min CPU)
python -m app.ml.train_transformer --with-synthetic --holdout CEAS_08   # GPU, ~1 min; writes temperature
python -m app.ml.train_transformer --with-synthetic --final
python -m app.ml.eval_demo --model transformer         # score the team's demo emails
```

Extra deps beyond `requirements.txt`: `scikit-learn pandas joblib torch transformers`.

## Figures for the pitch

`python -m app.ml.figures` (from `backend/`) writes `figures/confusion_holdout.png`
(honest test) and `figures/demo_ml_vs_system.png` (text model alone vs the full
system on the team's demo emails). Re-run it after the demo emails change.
