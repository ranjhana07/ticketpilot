from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Plan = Literal["free", "team", "business", "enterprise"]


class Subscription(BaseModel):
    plan: Plan
    seats: int
    billing_cycle: Literal["monthly", "annual"]
    status: Literal["active", "cancelled"]
    renews_on: str | None = None
    cancel_at_period_end: bool = False


class Customer(BaseModel):
    id: str
    email: str
    name: str
    company: str = ""
    status: Literal["active", "locked", "suspended"]
    fraud_flag: bool = False
    created_at: str
    subscription: Subscription | None = None


class Order(BaseModel):
    id: str
    customer_id: str
    kind: str
    description: str
    amount: float
    currency: str
    status: str
    created_at: str
    refunded: float = 0.0

    @property
    def refundable(self) -> float:
        return round(self.amount - self.refunded, 2)


class VerifyRequest(BaseModel):
    requester_email: str


class VerifyResponse(BaseModel):
    verified: bool
    method: str
    customer_id: str


class RefundRequest(BaseModel):
    amount: float = Field(gt=0)
    reason: str = Field(min_length=3)
    issued_by: str = "agent"


class RefundResponse(BaseModel):
    refund_id: int
    order_id: str
    amount: float
    order_refunded_total: float
    status: str


class SubscriptionChange(BaseModel):
    plan: Plan
    billing_cycle: Literal["monthly", "annual"] | None = None
    seats: int | None = Field(default=None, ge=1)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3)


class PasswordResetResponse(BaseModel):
    status: str
    sent_to: str


class TicketCreate(BaseModel):
    id: str | None = None
    customer_email: str
    customer_name: str = ""
    subject: str
    body: str
    channel: str = "email"


class TicketPatch(BaseModel):
    status: str | None = None
    assignee: str | None = None
    triage: dict | None = None
    proposal: dict | None = None
    draft: dict | None = None
    thread_id: str | None = None


class NoteCreate(BaseModel):
    author: str = "agent"
    body: str = Field(min_length=1)


class EscalationCreate(BaseModel):
    team: Literal["billing", "security", "support_lead", "engineering", "sales"]
    reason: str = Field(min_length=3)
    escalated_by: str = "agent"
