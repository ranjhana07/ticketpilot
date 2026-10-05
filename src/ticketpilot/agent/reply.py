from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def parse_draft(text: str, allowed_citations: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    match = JSON_BLOCK.search(text)
    if match:
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            payload = {}
    reply = str(payload.get("reply") or "").strip()
    if not reply:
        reply = text.strip()
    cited = [str(item) for item in payload.get("citations", []) if str(item) in allowed_citations]
    unique = list(dict.fromkeys(cited))
    return {
        "reply": reply,
        "citations": unique,
        "needs_human_attention": bool(payload.get("needs_human_attention", False)),
    }
