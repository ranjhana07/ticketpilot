from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from ticketpilot.helpdesk.db import Database
from ticketpilot.helpdesk.schemas import (
    Customer,
    EscalationCreate,
    Order,
    PasswordResetResponse,
    RefundResponse,
    Subscription,
    SubscriptionChange,
    TicketCreate,
    TicketPatch,
    VerifyResponse,
)

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

    def reset_password(self, customer_id: str, actor: str = "agent") -> PasswordResetResponse:
        customer = self.get_customer(customer_id)
        if customer.fraud_flag:
            raise Forbidden("account is flagged for review and cannot be reset through support")
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO password_resets (customer_id, sent_to, created_at) VALUES (?, ?, ?)",
                (customer.id, customer.email, self._stamp()),
            )
            if customer.status == "locked":
                connection.execute("UPDATE customers SET status = 'active' WHERE id = ?", (customer.id,))
            self._audit(connection, actor, "reset_password", customer.id, {"sent_to": customer.email})
        return PasswordResetResponse(status="sent", sent_to=customer.email)

    def update_subscription(self, customer_id: str, change: SubscriptionChange, actor: str = "agent") -> Subscription:
        customer = self.get_customer(customer_id)
        if change.plan == "enterprise":
            raise Forbidden("enterprise plans are arranged by the sales team")
        if customer.subscription is None:
            raise NotFound("customer has no subscription")
        if customer.subscription.status != "active":
            raise Conflict("subscription is not active")
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE subscriptions SET plan = ?, billing_cycle = COALESCE(?, billing_cycle), seats = COALESCE(?, seats) "
                "WHERE customer_id = ?",
                (change.plan, change.billing_cycle, change.seats, customer_id),
            )
            self._audit(connection, actor, "update_subscription", customer_id, change.model_dump(exclude_none=True))
            subscription = self._subscription(connection, customer_id)
        return subscription

    def cancel_subscription(self, customer_id: str, reason: str, actor: str = "agent") -> Subscription:
        customer = self.get_customer(customer_id)
        if customer.subscription is None or customer.subscription.status != "active":
            raise Conflict("no active subscription to cancel")
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE subscriptions SET cancel_at_period_end = 1 WHERE customer_id = ?", (customer_id,)
            )
            self._audit(connection, actor, "cancel_subscription", customer_id, {"reason": reason})
            subscription = self._subscription(connection, customer_id)
        return subscription

    @staticmethod
    def _ticket_from_row(row: sqlite3.Row) -> dict:
        def decode(value: str | None):
            return json.loads(value) if value else None

        return {
            "id": row["id"],
            "customer_email": row["customer_email"],
            "customer_name": row["customer_name"],
            "subject": row["subject"],
            "body": row["body"],
            "channel": row["channel"],
            "status": row["status"],
            "assignee": row["assignee"],
            "created_at": row["created_at"],
            "triage": decode(row["triage_json"]),
            "proposal": decode(row["proposal_json"]),
            "draft": decode(row["draft_json"]),
            "thread_id": row["thread_id"],
        }

    def create_ticket(self, payload: TicketCreate) -> dict:
        with self.db.transaction() as connection:
            ticket_id = payload.id
            if ticket_id is None:
                count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
                ticket_id = f"TCK-{1000 + count + 1}"
            if connection.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone():
                raise Conflict(f"ticket {ticket_id} already exists")
            connection.execute(
                "INSERT INTO tickets (id, customer_email, customer_name, subject, body, channel, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ticket_id, payload.customer_email, payload.customer_name, payload.subject, payload.body,
                 payload.channel, self._stamp()),
            )
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return self._ticket_from_row(row)

    def get_ticket(self, ticket_id: str) -> dict:
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise NotFound(f"ticket {ticket_id} not found")
            return self._ticket_from_row(row)

    def list_tickets(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM tickets"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        with self.db.transaction() as connection:
            rows = connection.execute(query + " ORDER BY created_at DESC, id DESC", params).fetchall()
            return [self._ticket_from_row(row) for row in rows]

    def patch_ticket(self, ticket_id: str, patch: TicketPatch) -> dict:
        self.get_ticket(ticket_id)
        columns = {
            "status": patch.status,
            "assignee": patch.assignee,
            "thread_id": patch.thread_id,
            "triage_json": json.dumps(patch.triage) if patch.triage is not None else None,
            "proposal_json": json.dumps(patch.proposal) if patch.proposal is not None else None,
            "draft_json": json.dumps(patch.draft) if patch.draft is not None else None,
        }
        updates = {name: value for name, value in columns.items() if value is not None}
        if updates:
            assignments = ", ".join(f"{name} = ?" for name in updates)
            with self.db.transaction() as connection:
                connection.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", (*updates.values(), ticket_id))
        return self.get_ticket(ticket_id)

    def add_note(self, ticket_id: str, author: str, body: str) -> dict:
        self.get_ticket(ticket_id)
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO notes (ticket_id, author, body, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, author, body, self._stamp()),
            )
            self._audit(connection, author, "add_internal_note", ticket_id, {"note_id": cursor.lastrowid})
            return {"id": cursor.lastrowid, "ticket_id": ticket_id, "author": author, "body": body}

    def list_notes(self, ticket_id: str) -> list[dict]:
        self.get_ticket(ticket_id)
        with self.db.transaction() as connection:
            rows = connection.execute("SELECT * FROM notes WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
            return [dict(row) for row in rows]

    def escalate(self, ticket_id: str, payload: EscalationCreate) -> dict:
        self.get_ticket(ticket_id)
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO escalations (ticket_id, team, reason, escalated_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (ticket_id, payload.team, payload.reason, payload.escalated_by, self._stamp()),
            )
            connection.execute("UPDATE tickets SET status = 'escalated', assignee = ? WHERE id = ?", (payload.team, ticket_id))
            self._audit(connection, payload.escalated_by, "escalate_to_human", ticket_id, payload.model_dump())
            return {"id": cursor.lastrowid, "ticket_id": ticket_id, "team": payload.team, "status": "escalated"}

    def audit_log(self, limit: int = 200) -> list[dict]:
        with self.db.transaction() as connection:
            rows = connection.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) | {"detail": json.loads(row["detail"])} for row in rows]
