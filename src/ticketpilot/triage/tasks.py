from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ticketpilot.data import bitext
from ticketpilot.data.splits import stratified_split, subsample_per_class
from ticketpilot.data.synthetic import generate_tickets


@dataclass(frozen=True)
class Split:
    train_texts: list[str]
    train_labels: list[str]
    test_texts: list[str]
    test_labels: list[str]


@dataclass(frozen=True)
class TaskSpec:
    name: str
    description: str
    load: Callable[[], Split]


def _bitext_intent(per_class: int = 150, test_size: int = 1500, seed: int = 42) -> Split:
    tickets = bitext.load_tickets()
    train = subsample_per_class(tickets, key=lambda t: t.intent or "", per_class=per_class, seed=seed)
    used = {t.ticket_id for t in train}
    remaining = [t for t in tickets if t.ticket_id not in used]
    _, test = stratified_split(remaining, key=lambda t: t.intent or "", test_size=test_size / len(remaining), seed=seed)
    return Split(
        [t.text for t in train], [t.intent or "" for t in train],
        [t.text for t in test], [t.intent or "" for t in test],
    )


def _synthetic(label: str, train_size: int = 4000, test_size: int = 1200) -> Split:
    train = generate_tickets(train_size, seed=101)
    test = generate_tickets(test_size, seed=202)
    return Split(
        [t.text for t in train], [getattr(t, label) or "" for t in train],
        [t.text for t in test], [getattr(t, label) or "" for t in test],
    )


TASKS: dict[str, TaskSpec] = {
    "bitext_intent": TaskSpec("bitext_intent", "27 intents on the public Bitext dataset", _bitext_intent),
    "synthetic_intent": TaskSpec("synthetic_intent", "12 intents on generated Loomwork tickets", lambda: _synthetic("intent")),
    "synthetic_priority": TaskSpec("synthetic_priority", "4 priority levels on generated Loomwork tickets", lambda: _synthetic("priority")),
}


def model_path(models_dir: Path, task: str, kind: str) -> Path:
    suffix = ".joblib" if kind == "baseline" else ""
    return models_dir / task / f"{kind}{suffix}"
