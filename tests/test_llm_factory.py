from dataclasses import replace

import pytest

from ticketpilot.agent.llm import build_llm
from ticketpilot.agent.scripted import ScriptedSupportModel
from ticketpilot.config import Settings


def test_scripted_provider():
    assert isinstance(build_llm(replace(Settings(), llm_provider="scripted")), ScriptedSupportModel)


def test_anthropic_needs_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_llm(replace(Settings(), llm_provider="anthropic"))


def test_anthropic_model_comes_from_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm = build_llm(replace(Settings(), llm_provider="anthropic", model="claude-sonnet-5-5"))
    assert llm.model == "claude-sonnet-5-5"


def test_default_model_is_sonnet(monkeypatch):
    monkeypatch.delenv("TICKETPILOT_MODEL", raising=False)
    assert Settings().model == "claude-sonnet-5-5"


def test_unknown_provider():
    with pytest.raises(ValueError):
        build_llm(replace(Settings(), llm_provider="other"))
