from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from ticketpilot.helpdesk.db import Database
from ticketpilot.helpdesk.schemas import Customer, Order, RefundResponse, Subscription, VerifyResponse

Clock = Callable[[], datetime]

REFUNDABLE_STATUSES = ("paid", "provisioned")


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Forbidden(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cents(amount: float) -> int:
    return int(round(amount * 100))


class HelpdeskService:
    def __init__(self, database: Database, clock: Clock = utc_now) -> None:
        self.db = database
        self.clock = clock

    def _stamp(self) -> str:
        return self.clock().isoformat(timespec="seconds")

    def _audit(self, connection: sqlite3.Connection, actor: str, action: str, target: str, detail: dict) -> None:
        connection.execute(
            "INSERT INTO audit_log (ts, actor, action, target, detail) VALUES (?, ?, ?, ?, ?)",
            (self._stamp(), actor, action, target, json.dumps(detail)),
        )

    def _subscription(self, connection: sqlite3.Connection, customer_id: str) -> Subscription | None:
        row = connection.execute("SELECT * FROM subscriptions WHERE customer_id = ?", (customer_id,)).fetchone()
        if row is None:
            return None
        return Subscription(
            plan=row["plan"],
            seats=row["seats"],
            billing_cycle=row["billing_cycle"],
            status=row["status"],
            renews_on=row["renews_on"],
            cancel_at_period_end=bool(row["cancel_at_period_end"]),
        )

    def _customer_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Customer:
        return Customer(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            company=row["company"],
            status=row["status"],
            fraud_flag=bool(row["fraud_flag"]),
            created_at=row["created_at"],
            subscription=self._subscription(connection, row["id"]),
        )

    def get_customer(self, customer_id: str) -> Customer:
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if row is None:
                raise NotFound(f"customer {customer_id} not found")
            return self._customer_from_row(connection, row)

    def lookup_customer(self, email: str) -> Customer:
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM customers WHERE lower(email) = lower(?)", (email.strip(),)).fetchone()
            if row is None:
                raise NotFound(f"no customer with email {email}")
            return self._customer_from_row(connection, row)

    def verify_identity(self, customer_id: str, requester_email: str) -> VerifyResponse:
        customer = self.get_customer(customer_id)
        matched = customer.email.lower() == requester_email.strip().lower() and customer.status != "suspended"
        with self.db.transaction() as connection:
            self._audit(connection, "agent", "verify_identity", customer_id, {"verified": matched})
        return VerifyResponse(verified=matched, method="sender_email_match", customer_id=customer_id)

    @staticmethod
    def _order_from_row(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            customer_id=row["customer_id"],
            kind=row["kind"],
            description=row["description"],
            amount=row["amount_cents"] / 100,
            currency=row["currency"],
            status=row["status"],
            created_at=row["created_at"],
            refunded=row["refunded_cents"] / 100,
        )

    def get_order(self, order_id: str) -> Order:
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id.upper(),)).fetchone()
            if row is None:
                raise NotFound(f"order {order_id} not found")
            return self._order_from_row(row)

    def list_orders(self, customer_id: str) -> list[Order]:
        self.get_customer(customer_id)
        with self.db.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,)
            ).fetchall()
            return [self._order_from_row(row) for row in rows]

    def refund_order(self, order_id: str, amount: float, reason: str, issued_by: str) -> RefundResponse:
        requested = cents(amount)
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id.upper(),)).fetchone()
            if row is None:
                raise NotFound(f"order {order_id} not found")
            if row["status"] not in REFUNDABLE_STATUSES:
                raise Conflict(f"order {row['id']} is {row['status']} and cannot be refunded")
            remaining = row["amount_cents"] - row["refunded_cents"]
            if requested > remaining:
                raise Conflict(f"refund of {amount:.2f} exceeds the refundable balance of {remaining / 100:.2f}")
            cursor = connection.execute(
                "INSERT INTO refunds (order_id, amount_cents, reason, issued_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (row["id"], requested, reason, issued_by, self._stamp()),
            )
            refunded_total = row["refunded_cents"] + requested
            status = "refunded" if refunded_total == row["amount_cents"] else row["status"]
            connection.execute(
                "UPDATE orders SET refunded_cents = ?, status = ? WHERE id = ?", (refunded_total, status, row["id"])
            )
            self._audit(
                connection, issued_by, "refund_order", row["id"], {"amount": requested / 100, "reason": reason}
            )
            return RefundResponse(
                refund_id=cursor.lastrowid,
                order_id=row["id"],
                amount=requested / 100,
                order_refunded_total=refunded_total / 100,
                status=status,
            )
