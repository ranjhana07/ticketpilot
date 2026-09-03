from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class TransformerClassifier:
    def __init__(self, model_name: str = DEFAULT_MODEL, max_length: int = 64) -> None:
        self.model_name = model_name
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = None
        self.classes: list[str] = []

    def _encode(self, texts: Sequence[str]):
        return self.tokenizer(
            list(texts), padding=True, truncation=True, max_length=self.max_length, return_tensors="pt"
        )

    def fit(
        self,
        texts: Sequence[str],
        labels: Sequence[str],
        epochs: int = 3,
        batch_size: int = 32,
        learning_rate: float = 5e-5,
        seed: int = 42,
        on_epoch: Callable[[int, float, float], None] | None = None,
    ) -> "TransformerClassifier":
        _seed_everything(seed)
        self.classes = sorted(set(labels))
        index = {label: position for position, label in enumerate(self.classes)}
        targets = torch.tensor([index[label] for label in labels])
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            num_labels=len(self.classes),
            id2label=dict(enumerate(self.classes)),
            label2id=index,
        )
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate, weight_decay=0.01)
        steps = epochs * ((len(texts) + batch_size - 1) // batch_size)
        scheduler = get_linear_schedule_with_warmup(optimizer, int(0.06 * steps), steps)
        order = list(range(len(texts)))
        for epoch in range(epochs):
            self.model.train()
            random.shuffle(order)
            started = time.time()
            running = 0.0
            for start in range(0, len(order), batch_size):
                batch = order[start:start + batch_size]
                encoded = self._encode([texts[i] for i in batch])
                output = self.model(**encoded, labels=targets[batch])
                output.loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                running += float(output.loss) * len(batch)
            if on_epoch:
                on_epoch(epoch + 1, running / len(texts), time.time() - started)
        self.model.eval()
        return self

    @torch.no_grad()
    def predict_proba(self, texts: Sequence[str], batch_size: int = 64) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("model is not trained or loaded")
        self.model.eval()
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        result = np.zeros((len(texts), len(self.classes)), dtype=np.float32)
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            logits = self.model(**self._encode([texts[i] for i in batch])).logits
            result[batch] = torch.softmax(logits, dim=-1).numpy()
        return result

    def predict(self, texts: Sequence[str]) -> list[str]:
        return [self.classes[i] for i in self.predict_proba(texts).argmax(axis=1)]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(directory)
        self.tokenizer.save_pretrained(directory)
        (directory / "classes.json").write_text(json.dumps(self.classes), encoding="utf-8")
        (directory / "meta.json").write_text(
            json.dumps({"base_model": self.model_name, "max_length": self.max_length}), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path) -> "TransformerClassifier":
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        instance = cls.__new__(cls)
        instance.model_name = meta["base_model"]
        instance.max_length = meta["max_length"]
        instance.tokenizer = AutoTokenizer.from_pretrained(directory)
        instance.model = AutoModelForSequenceClassification.from_pretrained(directory)
        instance.model.eval()
        instance.classes = json.loads((directory / "classes.json").read_text(encoding="utf-8"))
        return instance
