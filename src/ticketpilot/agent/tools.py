from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ticketpilot.agent.client import HelpdeskClient, HelpdeskError
from ticketpilot.data.schemas import Ticket
from ticketpilot.kb.retriever import HybridRetriever

READ_TOOLS = frozenset({"lookup_customer", "get_order", "list_customer_orders", "search_knowledge_base"})
ACCOUNT_CHANGING_TOOLS = frozenset({"refund_order", "reset_password", "update_subscription", "cancel_subscription"})


class LookupCustomerArgs(BaseModel):
    email: str = Field(description="Email address of the customer to look up")


class GetOrderArgs(BaseModel):
    order_id: str = Field(description="Order number such as ORD-48213")


class ListOrdersArgs(BaseModel):
    customer_id: str = Field(description="Customer id such as C-1001")


class VerifyIdentityArgs(BaseModel):
    customer_id: str = Field(description="Customer id to verify against the sender of this ticket")


class RefundOrderArgs(BaseModel):
    order_id: str = Field(description="Order number to refund")
    amount: float = Field(gt=0, description="Refund amount in USD, at most the order balance")
    reason: str = Field(min_length=3, description="Short reason recorded on the refund")


class ResetPasswordArgs(BaseModel):
    customer_id: str = Field(description="Customer whose password reset link should be sent")


class UpdateSubscriptionArgs(BaseModel):
    customer_id: str
    plan: Literal["free", "team", "business", "enterprise"]
    billing_cycle: Literal["monthly", "annual"] | None = None


class CancelSubscriptionArgs(BaseModel):
    customer_id: str
    reason: str = Field(min_length=3)


class EscalateArgs(BaseModel):
    team: Literal["billing", "security", "support_lead", "engineering", "sales"]
    reason: str = Field(min_length=3, description="What the human needs to know to pick this up")


class AddNoteArgs(BaseModel):
    note: str = Field(min_length=1, description="Internal note visible to agents only")


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(description="Question in plain language")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: type[BaseModel]


def _guarded(call: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(**kwargs: Any) -> Any:
        try:
            return call(**kwargs)
        except HelpdeskError as error:
            return {"error": error.detail, "status": error.status}

    return wrapper


class ToolBox:
    def __init__(self, client: HelpdeskClient, retriever: HybridRetriever | None = None) -> None:
        self.client = client
        self.retriever = retriever

    def tools_for(self, ticket: Ticket) -> list[StructuredTool]:
        client = self.client
        handlers: dict[str, Callable[..., Any]] = {
            "lookup_customer": lambda email: client.lookup_customer(email),
            "get_order": lambda order_id: client.get_order(order_id),
            "list_customer_orders": lambda customer_id: client.list_orders(customer_id),
            "verify_identity": lambda customer_id: client.verify_identity(customer_id, ticket.from_email),
            "refund_order": lambda order_id, amount, reason: client.refund_order(order_id, amount, reason),
            "reset_password": lambda customer_id: client.reset_password(customer_id),
            "update_subscription": lambda customer_id, plan, billing_cycle=None: client.update_subscription(
                customer_id, plan, billing_cycle
            ),
            "cancel_subscription": lambda customer_id, reason: client.cancel_subscription(customer_id, reason),
            "escalate_to_human": lambda team, reason: client.escalate(ticket.ticket_id, team, reason),
            "add_internal_note": lambda note: client.add_note(ticket.ticket_id, note),
            "search_knowledge_base": self._search,
        }
        return [
            StructuredTool.from_function(
                func=_guarded(handlers[spec.name]),
                name=spec.name,
                description=spec.description,
                args_schema=spec.schema,
            )
            for spec in TOOL_SPECS
        ]

    def _search(self, query: str) -> list[dict]:
        if self.retriever is None:
            return []
        return [hit.to_dict() for hit in self.retriever.search(query, k=3)]


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec("lookup_customer", "Find the customer record, plan and status for an email address. Only the sender's own address can be looked up.", LookupCustomerArgs),
    ToolSpec("verify_identity", "Check that the sender of this ticket is the owner of the given customer account. Required before any account change.", VerifyIdentityArgs),
    ToolSpec("get_order", "Get an order with its amount, status, age and refunded balance.", GetOrderArgs),
    ToolSpec("list_customer_orders", "List recent orders of a verified customer.", ListOrdersArgs),
    ToolSpec("refund_order", "Refund part or all of an order. Small amounts are issued directly, larger ones wait for human approval.", RefundOrderArgs),
    ToolSpec("reset_password", "Send a password reset link to the email address on file. Never sets a password.", ResetPasswordArgs),
    ToolSpec("update_subscription", "Change the plan or billing cycle of a verified customer. Enterprise is not available here.", UpdateSubscriptionArgs),
    ToolSpec("cancel_subscription", "Cancel the subscription at the end of the current period. Always needs human approval.", CancelSubscriptionArgs),
    ToolSpec("escalate_to_human", "Hand the ticket to a human team when policy blocks the action or the request is unusual.", EscalateArgs),
    ToolSpec("add_internal_note", "Write an internal note on the ticket for the human reviewer.", AddNoteArgs),
    ToolSpec("search_knowledge_base", "Search help center articles for policy and how-to answers.", SearchKnowledgeBaseArgs),
]
