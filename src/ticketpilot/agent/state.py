from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    ticket: dict[str, Any]
    triage: dict[str, Any]
    pii_mapping: dict[str, str]
    kb_hits: list[dict[str, Any]]
    messages: Annotated[list[AnyMessage], add_messages]
    verified_customers: list[str]
    decisions: dict[str, dict[str, Any]]
    actions: Annotated[list[dict[str, Any]], operator.add]
    draft: dict[str, Any]
    status: str
    steps: int
