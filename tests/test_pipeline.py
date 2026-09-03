import pytest

from ticketpilot.data.schemas import Ticket
from ticketpilot.data.synthetic import generate_tickets
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.triage.baseline import TfidfLogRegClassifier
from ticketpilot.triage.duplicates import DuplicateDetector
from ticketpilot.triage.pipeline import TriagePipeline, load_pipeline


@pytest.fixture(scope="module")
def pipeline():
    tickets = generate_tickets(1200, seed=33)
    texts = [t.text for t in tickets]
    intent = TfidfLogRegClassifier().fit(texts, [t.intent for t in tickets])
    priority = TfidfLogRegClassifier().fit(texts, [t.priority for t in tickets])
    return TriagePipeline(intent, priority, DuplicateDetector(HashingEmbedder(), threshold=0.6))


def test_analyze_returns_redacted_text_and_labels(pipeline):
    ticket = Ticket(
        ticket_id="T1",
        subject="Refund request",
        body="Please refund $49.00 on ORD-55555.\nThanks,\nMaya Reed\nmaya.reed@brightfield.io\nPhone: +1 415 555 0132",
        from_email="maya.reed@brightfield.io",
        from_name="Maya Reed",
    )
    result = pipeline.analyze(ticket)
    assert result.intent == "billing_refund"
    assert {"EMAIL", "PHONE", "NAME"} <= set(result.pii_labels)
    assert "maya.reed" not in result.redacted_text
    assert result.language == "en"


class ConstantClassifier:
    def __init__(self, classes, winner):
        import numpy as np

        self.classes = classes
        self._row = np.array([1.0 if c == winner else 0.0 for c in classes])

    def predict_proba(self, texts):
        import numpy as np

        return np.tile(self._row, (len(texts), 1))


def test_urgent_language_bumps_priority(pipeline):
    priority_model = ConstantClassifier(["low", "normal", "high", "urgent"], "low")
    bumping = TriagePipeline(pipeline.intent_model, priority_model)
    ticket = Ticket(
        ticket_id="T2",
        subject="outage",
        body="URGENT!! production outage, we are blocked, fix this immediately, ASAP, emergency!!",
        from_email="a@x.io",
    )
    result = bumping.analyze(ticket)
    assert result.priority == "high"
    assert result.priority_bumped is True


def test_calm_text_keeps_model_priority(pipeline):
    priority_model = ConstantClassifier(["low", "normal", "high", "urgent"], "low")
    calm = TriagePipeline(pipeline.intent_model, priority_model)
    ticket = Ticket(ticket_id="T3", subject="", body="Do you offer student discounts?", from_email="a@x.io")
    result = calm.analyze(ticket)
    assert result.priority == "low" and not result.priority_bumped


def test_duplicates_are_reported(pipeline):
    first = Ticket(ticket_id="A", subject="", body="The reset link expired, please send a new password email", from_email="a@x.io")
    second = Ticket(ticket_id="B", subject="", body="reset link expired, please send me a new password email", from_email="a@x.io")
    pipeline.duplicate_detector.add([first])
    result = pipeline.analyze(second)
    assert [d["ticket_id"] for d in result.duplicates] == ["A"]


def test_load_pipeline_without_models_explains_how_to_train(tmp_path):
    with pytest.raises(FileNotFoundError, match="triage train"):
        load_pipeline(tmp_path)
