from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from ticketpilot.config import get_settings
from ticketpilot.data.synthetic import make_duplicate_pairs
from ticketpilot.embeddings import get_embedder
from ticketpilot.triage.duplicates import entities_conflict

THRESHOLDS = [round(0.1 + 0.01 * step, 2) for step in range(86)]


def _scores(embedder, pairs) -> np.ndarray:
    left = embedder.encode([a.text for a, _, _ in pairs])
    right = embedder.encode([b.text for _, b, _ in pairs])
    return (left * right).sum(axis=1)


def precision_recall(labels: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    true_positive = int((labels & predicted).sum())
    predicted_positive = int(predicted.sum())
    actual_positive = int(labels.sum())
    precision = true_positive / predicted_positive if predicted_positive else 0.0
    recall = true_positive / actual_positive if actual_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def best_threshold(scores: np.ndarray, labels: np.ndarray, allowed: np.ndarray) -> float:
    best, best_f1 = THRESHOLDS[0], -1.0
    for threshold in THRESHOLDS:
        f1 = precision_recall(labels, (scores >= threshold) & allowed)["f1"]
        if f1 > best_f1:
            best, best_f1 = threshold, f1
    return best


def evaluate(embedder_name: str, dev_pairs: int = 600, test_pairs: int = 900) -> list[dict[str, object]]:
    embedder = get_embedder(embedder_name)
    dev = make_duplicate_pairs(dev_pairs, seed=31)
    test = make_duplicate_pairs(test_pairs, seed=32)
    dev_scores, test_scores = _scores(embedder, dev), _scores(embedder, test)
    dev_labels = np.array([label for _, _, label in dev])
    test_labels = np.array([label for _, _, label in test])
    rows = []
    for guard in (False, True):
        dev_allowed = np.array([not (guard and entities_conflict(a, b)) for a, b, _ in dev])
        test_allowed = np.array([not (guard and entities_conflict(a, b)) for a, b, _ in test])
        threshold = best_threshold(dev_scores, dev_labels, dev_allowed)
        for name, value in (("tuned_on_dev", threshold), ("default_setting", get_settings().duplicate_threshold)):
            metrics = precision_recall(test_labels, (test_scores >= value) & test_allowed)
            rows.append(
                {
                    "embedder": embedder_name,
                    "entity_guard": guard,
                    "threshold_mode": name,
                    "threshold": value,
                    "n_pairs": len(test),
                    "n_positive": int(test_labels.sum()),
                    **metrics,
                }
            )
    return rows


def run(output_dir: Path, embedders: tuple[str, ...] = ("hashing", "minilm")) -> list[dict[str, object]]:
    rows = [row for name in embedders for row in evaluate(name)]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "duplicates.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (output_dir / "duplicates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows
