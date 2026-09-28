import pytest
from fastapi.testclient import TestClient

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.tools import ACCOUNT_CHANGING_TOOLS, READ_TOOLS, TOOL_SPECS, ToolBox
from ticketpilot.data.schemas import Ticket


@pytest.fixture()
def ticket():
    return Ticket(ticket_id="TCK-1001", subject="s", body="b", from_email="maya.reed@brightfield.io")


@pytest.fixture()
def toolbox(helpdesk):
    return ToolBox(HelpdeskClient(http=helpdesk))


def by_name(tools):
    return {tool.name: tool for tool in tools}


def test_every_spec_becomes_a_tool_with_schema(toolbox, ticket):
    tools = toolbox.tools_for(ticket)
    assert [t.name for t in tools] == [spec.name for spec in TOOL_SPECS]
    for tool in tools:
        assert tool.description
        assert tool.args_schema.model_json_schema()["properties"]


def test_hidden_context_is_not_exposed_to_the_model(toolbox, ticket):
    for tool in toolbox.tools_for(ticket):
        properties = tool.args_schema.model_json_schema()["properties"]
        assert "ticket_id" not in properties
        assert "requester_email" not in properties


def test_tool_categories_reference_real_tools():
    names = {spec.name for spec in TOOL_SPECS}
    assert READ_TOOLS <= names and ACCOUNT_CHANGING_TOOLS <= names
    assert not READ_TOOLS & ACCOUNT_CHANGING_TOOLS


def test_required_arguments_are_enforced(toolbox, ticket):
    refund = by_name(toolbox.tools_for(ticket))["refund_order"]
    required = refund.args_schema.model_json_schema()["required"]
    assert set(required) == {"order_id", "amount", "reason"}
    with pytest.raises(Exception):
        refund.invoke({"order_id": "ORD-1", "amount": -5, "reason": "bad"})


def test_plan_enum_rejects_unknown_values(toolbox, ticket):
    update = by_name(toolbox.tools_for(ticket))["update_subscription"]
    with pytest.raises(Exception):
        update.invoke({"customer_id": "C-1001", "plan": "platinum"})


def test_verify_identity_uses_ticket_sender(toolbox, ticket):
    verify = by_name(toolbox.tools_for(ticket))["verify_identity"]
    assert verify.invoke({"customer_id": "C-1001"})["verified"] is True
    assert verify.invoke({"customer_id": "C-1002"})["verified"] is False


def test_helpdesk_errors_become_tool_results(toolbox, ticket):
    get_order = by_name(toolbox.tools_for(ticket))["get_order"]
    result = get_order.invoke({"order_id": "ORD-00000"})
    assert result["status"] == 404 and "not found" in result["error"]


def test_escalation_binds_to_current_ticket(toolbox, ticket, helpdesk):
    escalate = by_name(toolbox.tools_for(ticket))["escalate_to_human"]
    result = escalate.invoke({"team": "billing", "reason": "needs a person"})
    assert result["ticket_id"] == "TCK-1001"
    assert helpdesk.get("/tickets/TCK-1001").json()["status"] == "escalated"
