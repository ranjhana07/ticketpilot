from ticketpilot.data.synthetic import generate_tickets
from ticketpilot.triage.baseline import TfidfLogRegClassifier
from ticketpilot.triage.metrics import classification_metrics


def test_baseline_learns_synthetic_intents(tmp_path):
    tickets = generate_tickets(900, seed=21)
    train, test = tickets[:700], tickets[700:]
    model = TfidfLogRegClassifier().fit([t.text for t in train], [t.intent for t in train])
    predictions = model.predict([t.text for t in test])
    metrics = classification_metrics([t.intent for t in test], predictions)
    assert metrics["accuracy"] > 0.8


def test_save_and_load_roundtrip(tmp_path):
    tickets = generate_tickets(300, seed=22)
    model = TfidfLogRegClassifier().fit([t.text for t in tickets], [t.intent for t in tickets])
    path = tmp_path / "model.joblib"
    model.save(path)
    loaded = TfidfLogRegClassifier.load(path)
    sample = [tickets[0].text, tickets[1].text]
    assert loaded.predict(sample) == model.predict(sample)
    assert loaded.predict_proba(sample).shape == (2, len(model.classes))


def test_metrics_shape():
    metrics = classification_metrics(["a", "b", "a"], ["a", "a", "a"])
    assert metrics["accuracy"] == round(2 / 3, 4)
    assert metrics["per_class"]["b"]["recall"] == 0.0
