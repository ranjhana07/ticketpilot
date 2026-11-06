from ticketpilot.evaluation.preprocessing_eval import evaluate_language, evaluate_redaction


def test_redaction_removes_injected_values():
    result = evaluate_redaction(count=400, seed=1)
    assert result["injected_values"] > 100
    assert result["recall"] >= 0.99
    assert result["tickets_without_pii_modified"] == 0


def test_language_detection_is_high_on_generated_text():
    result = evaluate_language(count=400, seed=2)
    assert result["accuracy"] >= 0.95
    assert set(result["per_language"]) == {"en", "es", "fr", "de"}
