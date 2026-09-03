from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Callable

from ticketpilot.triage.metrics import classification_metrics
from ticketpilot.triage.tasks import TASKS, Split
from ticketpilot.triage.train import train_baseline, train_transformer


def _timed_predict(model, texts: list[str]) -> tuple[list[str], float]:
    started = time.perf_counter()
    predictions = model.predict(texts)
    elapsed = time.perf_counter() - started
    return predictions, 1000.0 * elapsed / max(1, len(texts))


def evaluate_task(
    task: str,
    kinds: tuple[str, ...] = ("baseline", "transformer"),
    epochs: int = 3,
    log: Callable[[str], None] = print,
) -> list[dict[str, object]]:
    split: Split = TASKS[task].load()
    rows = []
    for kind in kinds:
        log(f"{task}: training {kind} on {len(split.train_texts)} examples")
        if kind == "baseline":
            model, train_seconds = train_baseline(split)
        else:
            model, train_seconds = train_transformer(
                split, epochs=epochs, on_epoch=lambda e, loss, secs: log(f"  epoch {e} loss {loss:.4f} ({secs:.0f}s)")
            )
        predictions, ms_per_ticket = _timed_predict(model, split.test_texts)
        metrics = classification_metrics(split.test_labels, predictions)
        rows.append(
            {
                "task": task,
                "model": kind,
                "n_train": len(split.train_texts),
                "n_test": len(split.test_texts),
                "n_classes": len(set(split.train_labels)),
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
                "train_seconds": round(train_seconds, 1),
                "inference_ms_per_ticket": round(ms_per_ticket, 3),
                "per_class": metrics["per_class"],
            }
        )
        log(f"  accuracy {metrics['accuracy']} macro_f1 {metrics['macro_f1']}")
    return rows


def write_results(rows: list[dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "triage.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    columns = [
        "task", "model", "n_train", "n_test", "n_classes", "accuracy", "macro_f1",
        "weighted_f1", "train_seconds", "inference_ms_per_ticket",
    ]
    with (output_dir / "triage.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(output_dir: Path, tasks: list[str] | None = None, epochs: int = 3) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task in tasks or list(TASKS):
        rows.extend(evaluate_task(task, epochs=epochs))
    write_results(rows, output_dir)
    return rows
