from datetime import datetime, timezone

import pytest

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.policy import PolicyConfig, PolicyContext, PolicyEngine
from ticketpilot.data.schemas import Ticket

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def engine(helpdesk):
    return PolicyEngine(HelpdeskClient(http=helpdesk), PolicyConfig(), clock=lambda: NOW)


def context(email: str, *verified: str) -> PolicyContext:
    ticket = Ticket(ticket_id="TCK-X", subject="", body="", from_email=email)
    return PolicyContext(ticket, set(verified))


def test_lookup_limited_to_sender_address(engine):
    ctx = context("maya.reed@brightfield.io")
    assert engine.evaluate("lookup_customer", {"email": "Maya.Reed@brightfield.io"}, ctx).allowed
    denied = engine.evaluate("lookup_customer", {"email": "daniel.okafor@northpeak.co"}, ctx)
    assert denied.verdict == "deny" and denied.rule == "lookup_scope"


@pytest.mark.parametrize(
    "tool,args",
    [
        ("reset_password", {"customer_id": "C-1001"}),
        ("update_subscription", {"customer_id": "C-1001", "plan": "business"}),
        ("cancel_subscription", {"customer_id": "C-1001", "reason": "budget"}),
        ("refund_order", {"order_id": "ORD-48213", "amount": 10.0, "reason": "mistake"}),
        ("get_order", {"order_id": "ORD-48213"}),
        ("list_customer_orders", {"customer_id": "C-1001"}),
    ],
)
def test_account_actions_need_verification(engine, tool, args):
    decision = engine.evaluate(tool, args, context("maya.reed@brightfield.io"))
    assert decision.verdict == "deny" and decision.rule == "identity_verification"


def test_verification_for_another_customer_does_not_carry_over(engine):
    args = {"order_id": "ORD-50111", "amount": 10.0, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("maya.reed@brightfield.io", "C-1001"))
    assert decision.rule == "identity_verification"


def test_small_refund_is_automatic(engine):
    args = {"order_id": "ORD-54001", "amount": 15.0, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("aisha.kim@oakmere.com", "C-1009"))
    assert decision.verdict == "allow"


def test_refund_just_above_limit_needs_approval(engine):
    args = {"order_id": "ORD-53010", "amount": 50.01, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("elena.silva@stonebridge.co", "C-1007"))
    assert decision.verdict == "require_approval" and decision.rule == "refund_approval"


def test_refund_above_ceiling_is_denied(engine):
    args = {"order_id": "ORD-52200", "amount": 1080.0, "reason": "overcharge"}
    decision = engine.evaluate("refund_order", args, context("omar.haddad@quillhouse.org", "C-1006"))
    assert decision.verdict == "deny" and decision.rule == "refund_ceiling"


def test_refund_cannot_exceed_balance(engine):
    args = {"order_id": "ORD-54001", "amount": 20.0, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("aisha.kim@oakmere.com", "C-1009"))
    assert decision.rule == "refund_balance"


def test_old_order_is_outside_window(engine):
    args = {"order_id": "ORD-49002", "amount": 20.0, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("daniel.okafor@northpeak.co", "C-1002"))
    assert decision.verdict == "deny" and decision.rule == "refund_window"


def test_unknown_order_is_denied(engine):
    args = {"order_id": "ORD-00000", "amount": 5.0, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("a@b.c", "C-1001"))
    assert decision.rule == "order_exists"


def test_cancellation_always_needs_approval(engine):
    args = {"customer_id": "C-1009", "reason": "budget"}
    decision = engine.evaluate("cancel_subscription", args, context("aisha.kim@oakmere.com", "C-1009"))
    assert decision.verdict == "require_approval"


def test_enterprise_plan_is_denied_even_when_verified(engine):
    args = {"customer_id": "C-1002", "plan": "enterprise"}
    decision = engine.evaluate("update_subscription", args, context("daniel.okafor@northpeak.co", "C-1002"))
    assert decision.rule == "enterprise_sales_only"


def test_safe_tools_are_always_allowed(engine):
    ctx = context("x@y.z")
    for tool in ("escalate_to_human", "add_internal_note", "search_knowledge_base", "verify_identity"):
        assert engine.evaluate(tool, {}, ctx).allowed


def test_automatic_refunds_cannot_be_split_to_dodge_the_limit(engine):
    ticket = Ticket(ticket_id="TCK-X", subject="", body="", from_email="elena.silva@stonebridge.co")
    args = {"order_id": "ORD-53010", "amount": 30.0, "reason": "mistake"}
    first = engine.evaluate("refund_order", args, PolicyContext(ticket, {"C-1007"}, refunded_so_far=0.0))
    second = engine.evaluate("refund_order", args, PolicyContext(ticket, {"C-1007"}, refunded_so_far=30.0))
    assert first.verdict == "allow"
    assert second.verdict == "require_approval"


def test_amount_is_rounded_to_cents_before_comparison(engine):
    args = {"order_id": "ORD-54001", "amount": 15.004, "reason": "mistake"}
    decision = engine.evaluate("refund_order", args, context("aisha.kim@oakmere.com", "C-1009"))
    assert decision.verdict == "allow"
