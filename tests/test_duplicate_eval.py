import numpy as np

from ticketpilot.evaluation.duplicate_eval import best_threshold, evaluate, precision_recall


def test_precision_recall_counts():
    labels = np.array([True, True, False, False])
    predicted = np.array([True, False, True, False])
    assert precision_recall(labels, predicted) == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_best_threshold_separates_scores():
    scores = np.array([0.9, 0.85, 0.4, 0.35])
    labels = np.array([True, True, False, False])
    allowed = np.ones(4, dtype=bool)
    threshold = best_threshold(scores, labels, allowed)
    assert 0.4 < threshold <= 0.85


def test_guard_never_lowers_precision_with_hashing_embedder():
    rows = evaluate("hashing", dev_pairs=90, test_pairs=120)
    fixed = {r["entity_guard"]: r for r in rows if r["threshold_mode"] == "default_setting"}
    assert fixed[True]["precision"] >= fixed[False]["precision"]
