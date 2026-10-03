"""Baseline phishing classifier: TF-IDF (words + characters) + logistic regression.

Trains on subject + body only. Sender, URLs and headers are Person A's
deterministic signals, and dates are dropped because every source corpus comes
from a different era (the year alone would reveal the label).

Usage (from backend/):
    python -m app.ml.train_baseline              # evaluate + save app/ml/models/baseline.joblib
    python -m app.ml.train_baseline --skip-eval  # only train and save the final model
"""
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, classification_report,
                             confusion_matrix, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ml.text import email_text, normalize

ROOT = Path(__file__).resolve().parents[3]  # repo root
RAW = ROOT / "data" / "raw"
SYNTHETIC = ROOT / "data" / "synthetic" / "modern_emails.csv"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "baseline.joblib"
SOURCES = ["CEAS_08", "Enron", "Ling", "Nazario", "Nigerian_Fraud", "SpamAssasin"]
# Holdout sources must contain both classes, otherwise precision/recall are meaningless.
HOLDOUT_SOURCES = ["CEAS_08", "SpamAssasin"]


def load(include_synthetic: bool = False) -> pd.DataFrame:
    frames = []
    for src in SOURCES:
        df = pd.read_csv(RAW / f"{src}.csv", encoding_errors="ignore", low_memory=False)
        df = df[["subject", "body", "label"]].copy()
        df["source"] = src
        frames.append(df)
    if include_synthetic:
        # Modern notification-style emails from app/ml/synth_emails.py (never used as a test source).
        syn = pd.read_csv(SYNTHETIC, encoding="utf-8")[["subject", "body", "label"]]
        syn["source"] = "Synthetic"
        frames.append(syn)
    df = pd.concat(frames, ignore_index=True)
    df["text"] = [normalize(email_text(s, b)) for s, b in
                  zip(df["subject"].fillna("").astype(str), df["body"].fillna("").astype(str))]
    df = df[df["text"].str.len() > 20]
    before = len(df)
    # Same text with conflicting labels across corpora: drop entirely, then keep one copy of each text.
    conflicting = df.groupby("text")["label"].transform("nunique") > 1
    df = df[~conflicting].drop_duplicates(subset="text")
    print(f"loaded {before} emails, {len(df)} after dedup "
          f"({conflicting.sum()} rows with conflicting labels, {before - len(df)} removed in total)")
    return df.reset_index(drop=True)


def build_pipeline() -> Pipeline:
    # Hashing instead of a stored vocabulary: the saved model has no 400k-entry dict to
    # unpickle, so it loads in well under the 2 s startup budget.
    features = FeatureUnion([
        ("words", Pipeline([
            ("hash", HashingVectorizer(ngram_range=(1, 2), n_features=2**20, alternate_sign=False,
                                       norm=None, strip_accents="unicode")),
            ("tfidf", TfidfTransformer(sublinear_tf=True)),
        ])),
        ("chars", Pipeline([
            ("hash", HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=2**20,
                                       alternate_sign=False, norm=None)),
            ("tfidf", TfidfTransformer(sublinear_tf=True)),
        ])),
    ])
    clf = LogisticRegression(C=4.0, max_iter=2000, solver="liblinear", class_weight="balanced")
    return Pipeline([("features", features), ("clf", clf)])


def report(name: str, y_true, proba, threshold: float = 0.5) -> None:
    pred = (proba >= threshold).astype(int)
    print(f"\n=== {name} (n={len(y_true)}) ===")
    print(f"ROC-AUC {roc_auc_score(y_true, proba):.4f} | PR-AUC {average_precision_score(y_true, proba):.4f}")
    print(classification_report(y_true, pred, target_names=["legit", "phishing"], digits=4))
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    print(f"confusion: TN={tn} FP={fp} FN={fn} TP={tp}")


def evaluate(df: pd.DataFrame) -> None:
    # 1) Random split: optimistic, because train and test share the same corpora.
    tr, te = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=42)
    t = time.time()
    model = build_pipeline().fit(tr["text"], tr["label"])
    print(f"\ntrained in {time.time() - t:.0f}s")
    report("random split (optimistic)", te["label"], model.predict_proba(te["text"])[:, 1])

    # 2) Leave-one-source-out: the honest number, the model has never seen this corpus.
    for src in HOLDOUT_SOURCES:
        tr, te = df[df.source != src], df[df.source == src]
        t = time.time()
        m = build_pipeline().fit(tr["text"], tr["label"])
        print(f"\ntrained without {src} in {time.time() - t:.0f}s")
        report(f"holdout source = {src} (honest)", te["label"], m.predict_proba(te["text"])[:, 1])


def main() -> None:
    df = load()
    print(df.groupby("source")["label"].value_counts().unstack(fill_value=0))
    if "--skip-eval" not in sys.argv:
        evaluate(df)

    # Final model on everything, saved for the backend.
    print("\ntraining final model on all data...")
    final = build_pipeline().fit(df["text"], df["label"])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": final, "normalize": "app.ml.text.normalize"}, MODEL_PATH, compress=3)
    t = time.time()
    joblib.load(MODEL_PATH)
    print(f"\nsaved {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1e6:.1f} MB), loads in {time.time() - t:.2f}s")


if __name__ == "__main__":
    main()
