from ticketpilot.config import Settings


def test_defaults(monkeypatch):
    for name in ("AUTO_REFUND_LIMIT_USD", "MAX_REFUND_USD", "REFUND_WINDOW_DAYS", "TICKETPILOT_LLM", "DUPLICATE_THRESHOLD"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.auto_refund_limit == 50.0
    assert settings.max_refund == 500.0
    assert settings.refund_window_days == 30
    assert settings.llm_provider == "anthropic"
    assert settings.duplicate_threshold == 0.4


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("AUTO_REFUND_LIMIT_USD", "25.5")
    monkeypatch.setenv("REFUND_WINDOW_DAYS", "14")
    monkeypatch.setenv("TICKETPILOT_KB_DIR", "/tmp/kb")
    settings = Settings()
    assert settings.auto_refund_limit == 25.5
    assert settings.refund_window_days == 14
    assert str(settings.kb_dir).replace("\\", "/").endswith("/tmp/kb")
