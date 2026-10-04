from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ticketpilot.config import Settings


def build_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "scripted":
        from ticketpilot.agent.scripted import ScriptedSupportModel

        return ScriptedSupportModel()
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.model, temperature=0, max_tokens=1500, timeout=60, max_retries=2)
    raise ValueError(f"unknown TICKETPILOT_LLM {settings.llm_provider!r}, expected 'anthropic' or 'scripted'")
