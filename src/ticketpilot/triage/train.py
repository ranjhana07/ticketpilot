from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from ticketpilot.triage.baseline import TfidfLogRegClassifier
from ticketpilot.triage.tasks import TASKS, Split, model_path
from ticketpilot.triage.transformer import DEFAULT_MODEL, TransformerClassifier


def train_baseline(split: Split) -> tuple[TfidfLogRegClassifier, float]:
    started = time.perf_counter()
    model = TfidfLogRegClassifier().fit(split.train_texts, split.train_labels)
    return model, time.perf_counter() - started


def train_transformer(
    split: Split,
    base_model: str = DEFAULT_MODEL,
    epochs: int = 3,
    on_epoch: Callable[[int, float, float], None] | None = None,
) -> tuple[TransformerClassifier, float]:
    started = time.perf_counter()
    model = TransformerClassifier(base_model).fit(
        split.train_texts, split.train_labels, epochs=epochs, on_epoch=on_epoch
    )
    return model, time.perf_counter() - started


def train_and_save(task: str, kind: str, models_dir: Path, epochs: int = 3) -> Path:
    split = TASKS[task].load()
    target = model_path(models_dir, task, kind)
    if kind == "baseline":
        model, _ = train_baseline(split)
    else:
        model, _ = train_transformer(split, epochs=epochs)
    model.save(target)
    return target
