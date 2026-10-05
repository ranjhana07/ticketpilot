from __future__ import annotations

import itertools
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

DRAFT_MARKER = "DRAFT_REPLY_MODE"
_call_ids = itertools.count(1)


def tool_call(name: str, **args: Any) -> dict[str, Any]:
    return {"name": name, "args": args, "id": f"call_{next(_call_ids):04d}", "type": "tool_call"}


def ai_with_calls(*calls: dict[str, Any], text: str = "") -> AIMessage:
    return AIMessage(content=text, tool_calls=list(calls))


def fresh_copy(message: AIMessage) -> AIMessage:
    calls = [{**call, "id": f"call_{next(_call_ids):04d}"} for call in message.tool_calls]
    return AIMessage(content=message.content, tool_calls=calls)


def is_draft_request(messages: Sequence[BaseMessage]) -> bool:
    return any(isinstance(m, SystemMessage) and DRAFT_MARKER in str(m.content) for m in messages)


class QueuedChatModel(BaseChatModel):
    agent_turns: list[AIMessage]
    draft_json: str = '{"reply": "Thanks for your message.", "citations": [], "needs_human_attention": false}'
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "queued-fake"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "QueuedChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        if is_draft_request(messages):
            reply = AIMessage(content=self.draft_json)
        else:
            reply = fresh_copy(self.agent_turns[min(self.cursor, len(self.agent_turns) - 1)])
            self.cursor += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])
