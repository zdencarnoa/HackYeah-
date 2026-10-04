"""Fine-tune DistilBERT for phishing classification (run on the GPU server).

Same data, cleaning and dedup as the baseline (subject + body only). The trained
model is saved to app/ml/models/transformer_syn/ and runs on CPU for inference.

Usage (from backend/, on the GPU server):
    python -m app.ml.train_transformer --with-synthetic --holdout CEAS_08  # honest eval + calibration
    python -m app.ml.train_transformer --with-synthetic --final            # train on everything and save

The --holdout run also fits a calibration temperature on the unseen source and
writes app/ml/models/temperature_<source>_syn.json; copy it into the final model
folder as temperature.json so inference returns honest percentages.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (average_precision_score, classification_report,
                             confusion_matrix, roc_auc_score)
from torch.utils.data import DataLoader
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_linear_schedule_with_warmup)

from app.ml.train_baseline import load

BASE_MODEL = "distilbert-base-uncased"
OUT_DIR = Path(__file__).resolve().parent / "models" / "transformer_syn"
MAX_LEN = 256


def batches(tokenizer, texts, labels, batch_size, shuffle):
    data = list(zip(texts, labels))

    def collate(items):
        enc = tokenizer([t for t, _ in items], truncation=True, max_length=MAX_LEN,
                        padding=True, return_tensors="pt")
        enc["labels"] = torch.tensor([y for _, y in items])
        return enc

    return DataLoader(data, batch_size=batch_size, shuffle=shuffle, collate_fn=collate, num_workers=2)


@torch.no_grad()
def predict_logits(model, loader, device):
    model.eval()
    out = []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items() if k != "labels"}
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            out.append(model(**batch).logits.float().cpu())
    return torch.cat(out)


def fit_temperature(logits: torch.Tensor, labels: np.ndarray) -> float:
    """Temperature scaling: one scalar T so that softmax(logits / T) gives honest probabilities.

    Fitted on a source the model never saw, so T reflects real-world uncertainty
    rather than the (over)confidence the model has on its own training corpora.
    """
    y = torch.tensor(labels)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(logits / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp())


def ece(proba: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    """Expected calibration error for the phishing probability."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(proba, edges) - 1, 0, bins - 1)
    return float(sum(abs(proba[idx == b].mean() - labels[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def train(tr, epochs, batch_size, lr, device):
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=2).to(device)
    loader = batches(tokenizer, tr["text"].tolist(), tr["label"].tolist(), batch_size, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    steps = epochs * len(loader)
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)

    for epoch in range(epochs):
        model.train()
        t, running = time.time(), 0.0
        for i, batch in enumerate(loader, 1):
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                loss = model(**batch).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad()
            running += loss.item()
            if i % 200 == 0:
                print(f"epoch {epoch + 1} step {i}/{len(loader)} loss {running / 200:.4f} "
                      f"({time.time() - t:.0f}s)", flush=True)
                running = 0.0
    return model, tokenizer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", help="source to hold out for honest evaluation, e.g. CEAS_08")
    ap.add_argument("--final", action="store_true", help="train on all data and save the model")
    ap.add_argument("--with-synthetic", action="store_true",
                    help="add data/synthetic/modern_emails.csv to the training data")
    ap.add_argument("--out", default=str(OUT_DIR), help="where to save the final model")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-5)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device} {torch.cuda.get_device_name(0) if device == 'cuda' else ''}")
    df = load(include_synthetic=args.with_synthetic)

    if args.holdout:
        tr, te = df[df.source != args.holdout], df[df.source == args.holdout]
        model, tokenizer = train(tr, args.epochs, args.batch_size, args.lr, device)
        logits = predict_logits(model, batches(tokenizer, te["text"].tolist(), te["label"].tolist(), 128, False), device)
        y = te["label"].to_numpy()
        proba = torch.softmax(logits, dim=-1)[:, 1].numpy()
        temperature = fit_temperature(logits, y)
        calibrated = torch.softmax(logits / temperature, dim=-1)[:, 1].numpy()
        print(f"\ntemperature T = {temperature:.3f} | ECE before {ece(proba, y):.4f} -> after {ece(calibrated, y):.4f}")
        print("share of predictions between 10% and 90%: "
              f"before {((proba > .1) & (proba < .9)).mean():.1%} -> after {((calibrated > .1) & (calibrated < .9)).mean():.1%}")
        temp_file = Path(args.out).parent / f"temperature_{args.holdout}{'_syn' if args.with_synthetic else ''}.json"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(json.dumps({"temperature": temperature, "fitted_on": args.holdout,
                                         "with_synthetic": args.with_synthetic}))
        print(f"saved {temp_file}")
        pred = (proba >= 0.5).astype(int)
        print(f"\n=== holdout source = {args.holdout} (honest) (n={len(y)}) ===")
        print(f"ROC-AUC {roc_auc_score(y, proba):.4f} | PR-AUC {average_precision_score(y, proba):.4f}")
        print(classification_report(y, pred, target_names=["legit", "phishing"], digits=4))
        tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
        print(f"confusion: TN={tn} FP={fp} FN={fn} TP={tp}")

    if args.final:
        model, tokenizer = train(df, args.epochs, args.batch_size, args.lr, device)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out)
        tokenizer.save_pretrained(out)
        print(f"saved to {out}")


if __name__ == "__main__":
    main()
