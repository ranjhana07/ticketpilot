from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

from ticketpilot.data.schemas import PRIORITIES, Ticket
from ticketpilot.triage.baseline import TfidfLogRegClassifier
from ticketpilot.triage.duplicates import DuplicateDetector
from ticketpilot.triage.language import detect_language
from ticketpilot.triage.pii import redact
from ticketpilot.triage.sentiment import score_text
from ticketpilot.triage.tasks import model_path
from ticketpilot.triage.text import clean_ticket_text

URGENCY_BUMP_THRESHOLD = 0.8


class TextClassifier(Protocol):
    classes: list[str]

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray: ...


@dataclass
class TriageResult:
    intent: str
    intent_confidence: float
    priority: str
    priority_confidence: float
    language: str
    sentiment: float
    sentiment_label: str
    urgency: float
    pii_labels: list[str]
    redacted_text: str
    top_intents: list[tuple[str, float]] = field(default_factory=list)
    duplicates: list[dict[str, object]] = field(default_factory=list)
    priority_bumped: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _top(model: TextClassifier, text: str, k: int = 3) -> list[tuple[str, float]]:
    probabilities = model.predict_proba([text])[0]
    order = np.argsort(-probabilities)[:k]
    return [(model.classes[int(i)], round(float(probabilities[i]), 4)) for i in order]


class TriagePipeline:
    def __init__(
        self,
        intent_model: TextClassifier,
        priority_model: TextClassifier,
        duplicate_detector: DuplicateDetector | None = None,
    ) -> None:
        self.intent_model = intent_model
        self.priority_model = priority_model
        self.duplicate_detector = duplicate_detector

    def analyze(self, ticket: Ticket) -> TriageResult:
        cleaned = clean_ticket_text(ticket.text)
        names = [ticket.from_name] if ticket.from_name else []
        redaction = redact(cleaned, known_names=names)
        language = detect_language(cleaned)
        sentiment = score_text(cleaned)
        intents = _top(self.intent_model, redaction.text)
        priorities = _top(self.priority_model, redaction.text, k=len(PRIORITIES))
        priority, priority_confidence = priorities[0]
        bumped = False
        if sentiment.urgency >= URGENCY_BUMP_THRESHOLD and PRIORITIES.index(priority) < PRIORITIES.index("high"):
            priority, bumped = "high", True
        duplicates = []
        if self.duplicate_detector is not None:
            duplicates = [asdict(match) for match in self.duplicate_detector.find(ticket)]
        return TriageResult(
            intent=intents[0][0],
            intent_confidence=intents[0][1],
            priority=priority,
            priority_confidence=priority_confidence,
            language=language.language,
            sentiment=sentiment.score,
            sentiment_label=sentiment.label,
            urgency=sentiment.urgency,
            pii_labels=sorted(redaction.labels),
            redacted_text=redaction.text,
            top_intents=intents,
            duplicates=duplicates,
            priority_bumped=bumped,
        )


def _load_classifier(models_dir: Path, task: str, prefer: str) -> TextClassifier:
    order = ["transformer", "baseline"] if prefer == "auto" else [prefer]
    for kind in order:
        path = model_path(models_dir, task, kind)
        if not path.exists():
            continue
        if kind == "baseline":
            return TfidfLogRegClassifier.load(path)
        from ticketpilot.triage.transformer import TransformerClassifier

        return TransformerClassifier.load(path)
    raise FileNotFoundError(f"no trained model for {task} in {models_dir}, run `ticketpilot triage train`")


def load_pipeline(models_dir: Path, prefer: str = "auto", duplicate_detector: DuplicateDetector | None = None) -> TriagePipeline:
    return TriagePipeline(
        _load_classifier(models_dir, "synthetic_intent", prefer),
        _load_classifier(models_dir, "synthetic_priority", prefer),
        duplicate_detector,
    )
