from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from ticketpilot.agent.client import HelpdeskClient, HelpdeskError
from ticketpilot.config import Settings
from ticketpilot.data.schemas import Ticket

Verdict = Literal["allow", "require_approval", "deny"]


@dataclass(frozen=True)
class PolicyConfig:
    auto_refund_limit: float = 50.0
    max_refund: float = 500.0
    refund_window_days: int = 30

    @classmethod
    def from_settings(cls, settings: Settings) -> "PolicyConfig":
        return cls(settings.auto_refund_limit, settings.max_refund, settings.refund_window_days)


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    rule: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.verdict == "allow"


@dataclass
class PolicyContext:
    ticket: Ticket
    verified_customers: set[str] = field(default_factory=set)


ALLOW = Decision("allow", "default", "no restriction applies")


def _deny(rule: str, reason: str) -> Decision:
    return Decision("deny", rule, reason)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyEngine:
    def __init__(
        self,
        client: HelpdeskClient,
        config: PolicyConfig | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.client = client
        self.config = config or PolicyConfig()
        self.clock = clock

    def evaluate(self, tool: str, args: dict[str, Any], context: PolicyContext) -> Decision:
        handler = getattr(self, f"_check_{tool}", None)
        return handler(args, context) if handler else ALLOW

    def _check_lookup_customer(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        if str(args.get("email", "")).strip().lower() != context.ticket.from_email.strip().lower():
            return _deny("lookup_scope", "customer lookups are limited to the address that sent the ticket")
        return ALLOW

    def _require_verified(self, customer_id: str, context: PolicyContext) -> Decision | None:
        if customer_id not in context.verified_customers:
            return _deny(
                "identity_verification",
                f"identity for {customer_id} is not verified, call verify_identity first and escalate if it fails",
            )
        return None

    def _check_get_order(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        try:
            order = self.client.get_order(str(args.get("order_id", "")))
        except HelpdeskError as error:
            return Decision("allow", "default", f"order lookup will report: {error.detail}")
        return self._require_verified(order["customer_id"], context) or ALLOW

    def _check_list_customer_orders(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        return self._require_verified(str(args.get("customer_id", "")), context) or ALLOW

    def _check_reset_password(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        return self._require_verified(str(args.get("customer_id", "")), context) or ALLOW

    def _check_update_subscription(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        failed = self._require_verified(str(args.get("customer_id", "")), context)
        if failed:
            return failed
        if args.get("plan") == "enterprise":
            return _deny("enterprise_sales_only", "enterprise plans are arranged by the sales team, escalate to sales")
        return ALLOW

    def _check_cancel_subscription(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        failed = self._require_verified(str(args.get("customer_id", "")), context)
        if failed:
            return failed
        return Decision("require_approval", "cancellation_approval", "cancellations always need a human to approve")

    def _check_refund_order(self, args: dict[str, Any], context: PolicyContext) -> Decision:
        try:
            order = self.client.get_order(str(args.get("order_id", "")))
        except HelpdeskError as error:
            return _deny("order_exists", error.detail)
        failed = self._require_verified(order["customer_id"], context)
        if failed:
            return failed
        amount = float(args.get("amount", 0))
        balance = round(order["amount"] - order["refunded"], 2)
        if order["status"] not in ("paid", "provisioned"):
            return _deny("order_status", f"order is {order['status']} and cannot be refunded")
        if amount > balance + 1e-9:
            return _deny("refund_balance", f"requested {amount:.2f} exceeds the refundable balance of {balance:.2f}")
        age_days = (self.clock() - _parse_time(order["created_at"])).days
        if age_days > self.config.refund_window_days:
            return _deny(
                "refund_window",
                f"order is {age_days} days old, the refund window is {self.config.refund_window_days} days",
            )
        if amount > self.config.max_refund:
            return _deny(
                "refund_ceiling",
                f"{amount:.2f} is above the {self.config.max_refund:.2f} limit for support, escalate to billing",
            )
        if amount > self.config.auto_refund_limit:
            return Decision(
                "require_approval",
                "refund_approval",
                f"refunds above {self.config.auto_refund_limit:.2f} need human approval",
            )
        return Decision("allow", "refund_auto_limit", f"within the {self.config.auto_refund_limit:.2f} automatic limit")
