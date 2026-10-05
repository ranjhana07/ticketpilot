from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ticketpilot.agent.graph import AgentDeps, build_graph
from ticketpilot.data.schemas import Ticket


@dataclass
class RunResult:
    thread_id: str
    status: str
    triage: dict[str, Any] = field(default_factory=dict)
    kb_hits: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    draft: dict[str, Any] | None = None
    verified_customers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class SupportAgent:
    def __init__(self, deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self.deps = deps
        self.checkpointer = checkpointer or InMemorySaver()
        self.graph = build_graph(deps, self.checkpointer)

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}

    def start(self, ticket: Ticket, thread_id: str | None = None) -> RunResult:
        thread_id = thread_id or f"thread-{uuid.uuid4().hex[:12]}"
        self.graph.invoke({"ticket": ticket.to_dict()}, self._config(thread_id))
        return self.snapshot(thread_id)

    def resume(self, thread_id: str, decisions: dict[str, str], reviewer: str = "reviewer") -> RunResult:
        if not self.pending(thread_id):
            raise ValueError(f"thread {thread_id} is not waiting for approval")
        payload = {"decisions": decisions, "reviewer": reviewer}
        self.graph.invoke(Command(resume=payload), self._config(thread_id))
        return self.snapshot(thread_id)

    def pending(self, thread_id: str) -> list[dict[str, Any]]:
        state = self.graph.get_state(self._config(thread_id))
        for task in state.tasks:
            for item in task.interrupts:
                return list(item.value.get("actions", []))
        return []

    def snapshot(self, thread_id: str) -> RunResult:
        state = self.graph.get_state(self._config(thread_id))
        values = state.values
        pending = self.pending(thread_id)
        status = "awaiting_approval" if pending else values.get("status", "unknown")
        return RunResult(
            thread_id=thread_id,
            status=status,
            triage=_jsonable(values.get("triage", {})),
            kb_hits=_jsonable(values.get("kb_hits", [])),
            actions=_jsonable(values.get("actions", [])),
            pending_approvals=_jsonable(pending),
            draft=_jsonable(values.get("draft")),
            verified_customers=list(values.get("verified_customers", [])),
        )
