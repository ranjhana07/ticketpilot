from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from ticketpilot.config import Settings


def build_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "scripted":
        from ticketpilot.agent.scripted import ScriptedSupportModel

        return ScriptedSupportModel()
    if settings.llm_provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set, export it or run with TICKETPILOT_LLM=scripted")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.model, temperature=0, max_tokens=1500, timeout=60, max_retries=2)
    raise ValueError(f"unknown TICKETPILOT_LLM {settings.llm_provider!r}, expected 'anthropic' or 'scripted'")
