from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ticketpilot.agent.policy import Decision, PolicyContext, PolicyEngine
from ticketpilot.agent.prompts import AGENT_SYSTEM_PROMPT, DRAFT_SYSTEM_PROMPT, draft_message, ticket_message
from ticketpilot.agent.reply import message_text, parse_draft
from ticketpilot.agent.state import AgentState
from ticketpilot.agent.tools import ToolBox
from ticketpilot.data.schemas import Ticket
from ticketpilot.kb.retriever import HybridRetriever
from ticketpilot.triage.pii import redact
from ticketpilot.triage.pipeline import TriagePipeline


SENDER_TOKEN = "[SENDER_EMAIL]"


@dataclass
class AgentDeps:
    llm: BaseChatModel
    toolbox: ToolBox
    policy: PolicyEngine
    triage: TriagePipeline | None = None
    retriever: HybridRetriever | None = None
    max_steps: int = 8
    enforce_policy: bool = True


def _ticket(state: AgentState) -> Ticket:
    return Ticket.from_dict(state["ticket"])


def _decision_dict(decision: Decision) -> dict[str, Any]:
    return {"verdict": decision.verdict, "rule": decision.rule, "reason": decision.reason}


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None):
    placeholder = Ticket(ticket_id="schema", subject="", body="", from_email="")
    bound_llm = deps.llm.bind_tools(deps.toolbox.tools_for(placeholder))

    def triage_node(state: AgentState) -> dict[str, Any]:
        ticket = _ticket(state)
        names = [ticket.from_name] if ticket.from_name else []
        text = ticket.text
        if ticket.from_email:
            text = re.sub(re.escape(ticket.from_email), SENDER_TOKEN, text, flags=re.IGNORECASE)
        redaction = redact(text, known_names=names)
        if deps.triage is not None:
            triage = deps.triage.analyze(ticket).to_dict()
        else:
            triage = {"intent": None, "priority": None, "language": "en"}
        triage["redacted_text"] = redaction.text
        return {
            "triage": triage,
            "pii_mapping": redaction.mapping,
            "verified_customers": [],
            "decisions": {},
            "steps": 0,
            "status": "triaged",
        }

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        triage = state["triage"]
        hits: list[dict[str, Any]] = []
        if deps.retriever is not None:
            hits = [hit.to_dict() for hit in deps.retriever.search(triage["redacted_text"], k=4)]
        message = HumanMessage(content=ticket_message(state["ticket"], triage, hits))
        return {"kb_hits": hits, "messages": [message]}

    def agent_node(state: AgentState) -> dict[str, Any]:
        response = bound_llm.invoke([SystemMessage(content=AGENT_SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response], "steps": state.get("steps", 0) + 1, "status": "running"}

    def after_agent(state: AgentState) -> Literal["guard", "draft"]:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None)
        if calls and state.get("steps", 0) <= deps.max_steps:
            return "guard"
        return "draft"

    def guard_node(state: AgentState) -> dict[str, Any]:
        refunded = sum(
            float(action["args"].get("amount", 0))
            for action in state.get("actions", [])
            if action["tool"] == "refund_order" and action["status"] == "executed"
        )
        context = PolicyContext(_ticket(state), set(state.get("verified_customers", [])), refunded)
        decisions: dict[str, dict[str, Any]] = {}
        for call in state["messages"][-1].tool_calls:
            if deps.enforce_policy:
                decision = deps.policy.evaluate(call["name"], call["args"], context)
            else:
                decision = Decision("allow", "policy_disabled", "policy enforcement is switched off")
            decisions[call["id"]] = _decision_dict(decision)
            if call["name"] == "refund_order" and decision.allowed:
                context.refunded_so_far += float(call["args"].get("amount", 0))
        return {"decisions": decisions}

    def after_guard(state: AgentState) -> Literal["approval", "tools"]:
        needs = any(item["verdict"] == "require_approval" for item in state["decisions"].values())
        return "approval" if needs else "tools"

    def approval_node(state: AgentState) -> dict[str, Any]:
        calls = {call["id"]: call for call in state["messages"][-1].tool_calls}
        pending = [
            {
                "call_id": call_id,
                "tool": calls[call_id]["name"],
                "args": calls[call_id]["args"],
                "rule": decision["rule"],
                "reason": decision["reason"],
            }
            for call_id, decision in state["decisions"].items()
            if decision["verdict"] == "require_approval"
        ]
        answer = interrupt({"type": "approval_request", "ticket_id": state["ticket"]["ticket_id"], "actions": pending})
        choices = answer.get("decisions", {}) if isinstance(answer, dict) else {}
        reviewer = answer.get("reviewer", "reviewer") if isinstance(answer, dict) else "reviewer"
        updated = dict(state["decisions"])
        for item in pending:
            call_id = item["call_id"]
            if choices.get(call_id) == "approve":
                updated[call_id] = {
                    "verdict": "allow",
                    "rule": "human_approved",
                    "reason": f"approved by {reviewer}",
                    "approved_by": reviewer,
                }
            else:
                updated[call_id] = {
                    "verdict": "deny",
                    "rule": "human_rejected",
                    "reason": f"rejected by {reviewer}",
                    "approved_by": reviewer,
                }
        return {"decisions": updated}

    def tools_node(state: AgentState) -> dict[str, Any]:
        ticket = _ticket(state)
        tools = {tool.name: tool for tool in deps.toolbox.tools_for(ticket)}
        verified = list(state.get("verified_customers", []))
        messages: list[ToolMessage] = []
        actions: list[dict[str, Any]] = []
        for call in state["messages"][-1].tool_calls:
            decision = state["decisions"][call["id"]]
            record = {
                "call_id": call["id"],
                "tool": call["name"],
                "args": call["args"],
                "rule": decision["rule"],
                "approved_by": decision.get("approved_by"),
            }
            if decision["verdict"] == "allow":
                result = tools[call["name"]].invoke(call["args"])
                failed = isinstance(result, dict) and "error" in result
                record.update(status="failed" if failed else "executed", result=result)
                if call["name"] == "verify_identity" and isinstance(result, dict) and result.get("verified"):
                    verified.append(call["args"]["customer_id"])
            else:
                result = {"blocked": True, "rule": decision["rule"], "reason": decision["reason"]}
                record.update(status="blocked", reason=decision["reason"])
            actions.append(record)
            messages.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call["id"], name=call["name"]))
        return {"messages": messages, "actions": actions, "verified_customers": verified}

    def draft_node(state: AgentState) -> dict[str, Any]:
        prompt = draft_message(state["ticket"], state["triage"], state.get("kb_hits", []), state.get("actions", []))
        response = deps.llm.invoke([SystemMessage(content=DRAFT_SYSTEM_PROMPT), HumanMessage(content=prompt)])
        allowed = {hit["article_id"] for hit in state.get("kb_hits", [])}
        draft = parse_draft(message_text(response), allowed)
        escalated = any(action["tool"] == "escalate_to_human" and action["status"] == "executed" for action in state.get("actions", []))
        return {"draft": draft, "status": "escalated" if escalated else "awaiting_review"}

    graph = StateGraph(AgentState)
    graph.add_node("triage", triage_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("agent", agent_node)
    graph.add_node("guard", guard_node)
    graph.add_node("approval", approval_node)
    graph.add_node("tools", tools_node)
    graph.add_node("draft", draft_node)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "retrieve")
    graph.add_edge("retrieve", "agent")
    graph.add_conditional_edges("agent", after_agent, {"guard": "guard", "draft": "draft"})
    graph.add_conditional_edges("guard", after_guard, {"approval": "approval", "tools": "tools"})
    graph.add_edge("approval", "tools")
    graph.add_edge("tools", "agent")
    graph.add_edge("draft", END)
    return graph.compile(checkpointer=checkpointer)
