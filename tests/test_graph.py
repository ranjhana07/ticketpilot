from datetime import datetime, timezone

import pytest

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.fakes import QueuedChatModel, ai_with_calls, tool_call
from ticketpilot.agent.graph import AgentDeps
from ticketpilot.agent.policy import PolicyConfig, PolicyEngine
from ticketpilot.agent.runner import SupportAgent
from ticketpilot.agent.tools import ToolBox
from ticketpilot.data.schemas import Ticket
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.kb.rerank import OverlapReranker
from ticketpilot.kb.retriever import HybridRetriever
from ticketpilot.config import get_settings

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
DRAFT = '{"reply": "Done, see the refund policy.", "citations": ["refund-policy", "not-in-hits"], "needs_human_attention": false}'


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever.from_directory(get_settings().kb_dir, HashingEmbedder(), OverlapReranker())


def make_agent(helpdesk, retriever, turns, **options):
    client = HelpdeskClient(http=helpdesk)
    deps = AgentDeps(
        llm=QueuedChatModel(agent_turns=turns, draft_json=DRAFT),
        toolbox=ToolBox(client, retriever),
        policy=PolicyEngine(client, PolicyConfig(), clock=lambda: NOW),
        retriever=retriever,
        **options,
    )
    return SupportAgent(deps)


def make_ticket(helpdesk, email="aisha.kim@oakmere.com", subject="Refund please", body="Refund ORD-54001 for $15.00 please") -> Ticket:
    created = helpdesk.post("/tickets", json={"customer_email": email, "subject": subject, "body": body}).json()
    return Ticket(ticket_id=created["id"], subject=subject, body=body, from_email=email)


def refund_turns(order_id, amount, customer_id):
    return [
        ai_with_calls(tool_call("verify_identity", customer_id=customer_id)),
        ai_with_calls(tool_call("refund_order", order_id=order_id, amount=amount, reason="customer request")),
        ai_with_calls(text="DONE"),
    ]


def test_small_refund_runs_without_approval(helpdesk, retriever):
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-54001", 15.0, "C-1009"))
    result = agent.start(make_ticket(helpdesk))
    assert result.status == "awaiting_review"
    assert [a["tool"] for a in result.actions] == ["verify_identity", "refund_order"]
    assert result.actions[1]["status"] == "executed"
    assert helpdesk.get("/orders/ORD-54001").json()["refunded"] == 15.0


def test_draft_citations_are_limited_to_retrieved_articles(helpdesk, retriever):
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-54001", 15.0, "C-1009"))
    result = agent.start(make_ticket(helpdesk))
    assert "not-in-hits" not in result.draft["citations"]
    assert set(result.draft["citations"]) <= {hit["article_id"] for hit in result.kb_hits}


def test_unverified_refund_is_blocked_and_nothing_changes(helpdesk, retriever):
    turns = [
        ai_with_calls(tool_call("refund_order", order_id="ORD-54001", amount=15.0, reason="customer request")),
        ai_with_calls(text="DONE"),
    ]
    agent = make_agent(helpdesk, retriever, turns)
    result = agent.start(make_ticket(helpdesk))
    assert result.actions[0]["status"] == "blocked"
    assert result.actions[0]["rule"] == "identity_verification"
    assert helpdesk.get("/orders/ORD-54001").json()["refunded"] == 0.0


def test_failed_verification_does_not_unlock_actions(helpdesk, retriever):
    turns = [
        ai_with_calls(tool_call("verify_identity", customer_id="C-1009")),
        ai_with_calls(tool_call("reset_password", customer_id="C-1009")),
        ai_with_calls(text="DONE"),
    ]
    agent = make_agent(helpdesk, retriever, turns)
    result = agent.start(make_ticket(helpdesk, email="intruder@example.com"))
    assert result.verified_customers == []
    assert result.actions[1]["status"] == "blocked"


def test_large_refund_pauses_for_approval_then_executes(helpdesk, retriever):
    ticket = make_ticket(helpdesk, email="elena.silva@stonebridge.co", body="Refund ORD-53010 for $450.00")
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-53010", 450.0, "C-1007"))
    paused = agent.start(ticket)
    assert paused.status == "awaiting_approval"
    assert paused.pending_approvals[0]["tool"] == "refund_order"
    assert paused.pending_approvals[0]["rule"] == "refund_approval"
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 0.0
    call_id = paused.pending_approvals[0]["call_id"]
    finished = agent.resume(paused.thread_id, {call_id: "approve"}, reviewer="sam")
    assert finished.status == "awaiting_review"
    assert finished.actions[-1]["status"] == "executed"
    assert finished.actions[-1]["approved_by"] == "sam"
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 450.0


def test_rejected_approval_blocks_the_action(helpdesk, retriever):
    ticket = make_ticket(helpdesk, email="elena.silva@stonebridge.co", body="Refund ORD-53010 for $450.00")
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-53010", 450.0, "C-1007"))
    paused = agent.start(ticket)
    call_id = paused.pending_approvals[0]["call_id"]
    finished = agent.resume(paused.thread_id, {call_id: "reject"}, reviewer="sam")
    assert finished.actions[-1]["status"] == "blocked"
    assert finished.actions[-1]["rule"] == "human_rejected"
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 0.0


def test_missing_decision_counts_as_rejection(helpdesk, retriever):
    ticket = make_ticket(helpdesk, email="elena.silva@stonebridge.co", body="Refund ORD-53010 for $450.00")
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-53010", 450.0, "C-1007"))
    paused = agent.start(ticket)
    finished = agent.resume(paused.thread_id, {})
    assert finished.actions[-1]["rule"] == "human_rejected"


def test_resume_without_pending_approval_is_an_error(helpdesk, retriever):
    agent = make_agent(helpdesk, retriever, refund_turns("ORD-54001", 15.0, "C-1009"))
    result = agent.start(make_ticket(helpdesk))
    with pytest.raises(ValueError):
        agent.resume(result.thread_id, {})


def test_step_budget_stops_runaway_tool_loops(helpdesk, retriever):
    looping = [ai_with_calls(tool_call("search_knowledge_base", query="refund"))]
    agent = make_agent(helpdesk, retriever, looping, max_steps=3)
    result = agent.start(make_ticket(helpdesk))
    assert result.status == "awaiting_review"
    assert len(result.actions) == 3


def test_escalation_sets_escalated_status(helpdesk, retriever):
    turns = [
        ai_with_calls(tool_call("escalate_to_human", team="security", reason="possible account takeover")),
        ai_with_calls(text="DONE"),
    ]
    agent = make_agent(helpdesk, retriever, turns)
    ticket = make_ticket(helpdesk, subject="Hacked", body="someone is in our account")
    result = agent.start(ticket)
    assert result.status == "escalated"
    assert helpdesk.get(f"/tickets/{ticket.ticket_id}").json()["status"] == "escalated"


def test_disabling_policy_lets_unsafe_calls_through(helpdesk, retriever):
    turns = [
        ai_with_calls(tool_call("refund_order", order_id="ORD-54001", amount=15.0, reason="customer request")),
        ai_with_calls(text="DONE"),
    ]
    agent = make_agent(helpdesk, retriever, turns, enforce_policy=False)
    result = agent.start(make_ticket(helpdesk))
    assert result.actions[0]["status"] == "executed"


def test_parallel_refunds_in_one_turn_share_the_automatic_limit(helpdesk, retriever):
    ticket = make_ticket(helpdesk, email="elena.silva@stonebridge.co", body="Refund ORD-53010")
    turns = [
        ai_with_calls(tool_call("verify_identity", customer_id="C-1007")),
        ai_with_calls(
            tool_call("refund_order", order_id="ORD-53010", amount=30.0, reason="first part"),
            tool_call("refund_order", order_id="ORD-53010", amount=30.0, reason="second part"),
        ),
        ai_with_calls(text="DONE"),
    ]
    paused = make_agent(helpdesk, retriever, turns).start(ticket)
    assert paused.status == "awaiting_approval"
    assert len(paused.pending_approvals) == 1
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 0.0
