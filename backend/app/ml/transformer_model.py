"""CPU inference wrapper for the fine-tuned DistilBERT phishing classifier."""
import json
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.ml.text import normalize

MODEL_DIR = Path(__file__).resolve().parent / "models" / "transformer_syn"
MAX_LEN = 256


class PhishingTransformer:
    def __init__(self, model, tokenizer, temperature: float = 1.0):
        self.model = model.eval()
        self.tokenizer = tokenizer
        self.temperature = temperature

    @classmethod
    def load(cls, path: Path = MODEL_DIR) -> "PhishingTransformer":
        # temperature.json comes from the --holdout run (fitted on an unseen source);
        # without it the raw model is overconfident and returns almost only 0% or 100%.
        temp_file = Path(path) / "temperature.json"
        temperature = json.loads(temp_file.read_text())["temperature"] if temp_file.exists() else 1.0
        return cls(AutoModelForSequenceClassification.from_pretrained(path), AutoTokenizer.from_pretrained(path),
                   temperature)

    @torch.no_grad()
    def predict_proba(self, texts: list[str]) -> list[float]:
        enc = self.tokenizer([normalize(t) for t in texts], truncation=True, max_length=MAX_LEN,
                             padding=True, return_tensors="pt")
        logits = self.model(**enc).logits / self.temperature
        return torch.softmax(logits, dim=-1)[:, 1].tolist()
