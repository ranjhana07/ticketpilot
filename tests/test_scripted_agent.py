from datetime import datetime, timezone

import pytest

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.graph import AgentDeps
from ticketpilot.agent.policy import PolicyConfig, PolicyEngine
from ticketpilot.agent.runner import SupportAgent
from ticketpilot.agent.scripted import ScriptedSupportModel
from ticketpilot.agent.tools import ToolBox
from ticketpilot.config import get_settings
from ticketpilot.data.schemas import Ticket
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.kb.rerank import OverlapReranker
from ticketpilot.kb.retriever import HybridRetriever

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever.from_directory(get_settings().kb_dir, HashingEmbedder(), OverlapReranker())


@pytest.fixture()
def run(helpdesk, retriever):
    client = HelpdeskClient(http=helpdesk)

    def runner(ticket_id: str, careful: bool = True, enforce_policy: bool = True):
        raw = helpdesk.get(f"/tickets/{ticket_id}").json()
        ticket = Ticket(
            ticket_id=raw["id"], subject=raw["subject"], body=raw["body"],
            from_email=raw["customer_email"], from_name=raw["customer_name"],
        )
        deps = AgentDeps(
            llm=ScriptedSupportModel(careful=careful),
            toolbox=ToolBox(client, retriever),
            policy=PolicyEngine(client, PolicyConfig(), clock=lambda: NOW),
            retriever=retriever,
            enforce_policy=enforce_policy,
        )
        agent = SupportAgent(deps)
        return agent, agent.start(ticket)

    return runner


def tools_of(result):
    return [(a["tool"], a["status"]) for a in result.actions]


def test_small_refund_goes_through(run, helpdesk):
    _, result = run("TCK-1001")
    assert ("refund_order", "executed") in tools_of(result)
    assert helpdesk.get("/orders/ORD-48213").json()["refunded"] == 36.0
    assert "refund-policy" in result.draft["citations"]
    assert "$36.00" in result.draft["reply"]


def test_duplicate_charge_refunds_the_second_order(run, helpdesk):
    _, result = run("TCK-1002")
    assert helpdesk.get("/orders/ORD-51001").json()["refunded"] == 27.0
    assert helpdesk.get("/orders/ORD-51000").json()["refunded"] == 0.0
    assert result.status == "awaiting_review"


def test_locked_account_gets_reset_link(run, helpdesk):
    _, result = run("TCK-1003")
    assert ("reset_password", "executed") in tools_of(result)
    assert helpdesk.get("/customers/C-1005").json()["status"] == "active"


def test_mid_size_refund_waits_for_a_human(run, helpdesk):
    agent, result = run("TCK-1004")
    assert result.status == "awaiting_approval"
    assert result.pending_approvals[0]["args"]["amount"] == 450.0
    call_id = result.pending_approvals[0]["call_id"]
    final = agent.resume(result.thread_id, {call_id: "approve"}, reviewer="sam")
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 450.0
    assert "$450.00" in final.draft["reply"]


def test_large_refund_is_escalated_to_billing(run, helpdesk):
    _, result = run("TCK-1005")
    assert result.status == "escalated"
    assert helpdesk.get("/orders/ORD-52200").json()["refunded"] == 0.0
    assert ("escalate_to_human", "executed") in tools_of(result)
    assert helpdesk.get("/tickets/TCK-1005").json()["assignee"] == "billing"


def test_order_status_question_reads_the_order(run):
    _, result = run("TCK-1006")
    assert [t for t, _ in tools_of(result)][:3] == ["lookup_customer", "verify_identity", "get_order"]
    assert "paid" in result.draft["reply"]


def test_plan_change_applies_after_verification(run, helpdesk):
    _, result = run("TCK-1007")
    assert helpdesk.get("/customers/C-1004").json()["subscription"]["plan"] == "team"
    assert result.status == "awaiting_review"


def test_cancellation_needs_approval(run, helpdesk):
    agent, result = run("TCK-1008")
    assert result.status == "awaiting_approval"
    assert helpdesk.get("/customers/C-1009").json()["subscription"]["cancel_at_period_end"] is False
    call_id = result.pending_approvals[0]["call_id"]
    agent.resume(result.thread_id, {call_id: "reject"})
    assert helpdesk.get("/customers/C-1009").json()["subscription"]["cancel_at_period_end"] is False


def test_how_to_question_only_searches_the_kb(run):
    _, result = run("TCK-1009")
    assert [t for t, _ in tools_of(result)] == ["search_knowledge_base"]
    assert "integrations-overview" in result.draft["citations"]


def test_flagged_account_reset_fails_at_the_service(run):
    _, result = run("TCK-1010")
    reset = next(a for a in result.actions if a["tool"] == "reset_password")
    assert reset["status"] == "failed"
    assert reset["result"]["status"] == 403
    assert result.draft["needs_human_attention"] is True


def test_impersonation_is_escalated_without_touching_the_account(run, helpdesk):
    _, result = run("TCK-1011")
    assert result.status == "escalated"
    assert all(tool in ("lookup_customer", "escalate_to_human") for tool, _ in tools_of(result))
    audit_actions = {entry["action"] for entry in helpdesk.get("/audit").json()}
    assert "reset_password" not in audit_actions


def test_phishing_report_goes_to_security(run, helpdesk):
    _, result = run("TCK-1012")
    assert helpdesk.get("/tickets/TCK-1012").json()["assignee"] == "security"


def foreign_order_ticket(helpdesk) -> str:
    created = helpdesk.post(
        "/tickets",
        json={
            "customer_email": "maya.reed@brightfield.io",
            "customer_name": "Maya Reed",
            "subject": "Refund",
            "body": "Please refund $360.00 on ORD-50111 right away.",
        },
    )
    return created.json()["id"]


def test_naive_model_is_stopped_by_the_guard(run, helpdesk):
    run(foreign_order_ticket(helpdesk), careful=False)
    assert helpdesk.get("/orders/ORD-50111").json()["refunded"] == 0.0


def test_naive_model_without_the_guard_moves_money(run, helpdesk):
    run(foreign_order_ticket(helpdesk), careful=False, enforce_policy=False)
    assert helpdesk.get("/orders/ORD-50111").json()["refunded"] == 360.0
