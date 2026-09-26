from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ticketpilot.helpdesk.db import Database
from ticketpilot.helpdesk.schemas import (
    CancelRequest,
    Customer,
    EscalationCreate,
    NoteCreate,
    Order,
    PasswordResetResponse,
    RefundRequest,
    RefundResponse,
    Subscription,
    SubscriptionChange,
    TicketCreate,
    TicketPatch,
    VerifyRequest,
    VerifyResponse,
)
from ticketpilot.helpdesk.seed import seed, seed_demo_tickets
from ticketpilot.helpdesk.service import Clock, Conflict, Forbidden, HelpdeskService, NotFound, utc_now


def create_app(db_path: str | Path = ":memory:", clock: Clock = utc_now, seed_data: bool = True) -> FastAPI:
    database = Database(db_path)
    service = HelpdeskService(database, clock)
    with database.transaction() as connection:
        has_customers = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if seed_data and not has_customers:
        seed(database, clock())
        seed_demo_tickets(database, clock())

    app = FastAPI(title="Loomwork helpdesk (mock)", version="0.1.0")
    app.state.service = service
    app.state.database = database

    @app.exception_handler(NotFound)
    async def not_found(_: Request, error: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(Conflict)
    async def conflict(_: Request, error: Conflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(Forbidden)
    async def forbidden(_: Request, error: Forbidden) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/customers/lookup", response_model=Customer)
    def lookup_customer(email: str) -> Customer:
        return service.lookup_customer(email)

    @app.get("/customers/{customer_id}", response_model=Customer)
    def get_customer(customer_id: str) -> Customer:
        return service.get_customer(customer_id)

    @app.get("/customers/{customer_id}/orders", response_model=list[Order])
    def list_orders(customer_id: str) -> list[Order]:
        return service.list_orders(customer_id)

    @app.post("/customers/{customer_id}/verify", response_model=VerifyResponse)
    def verify(customer_id: str, payload: VerifyRequest) -> VerifyResponse:
        return service.verify_identity(customer_id, payload.requester_email)

    @app.post("/customers/{customer_id}/reset-password", response_model=PasswordResetResponse)
    def reset_password(customer_id: str) -> PasswordResetResponse:
        return service.reset_password(customer_id)

    @app.put("/customers/{customer_id}/subscription", response_model=Subscription)
    def update_subscription(customer_id: str, change: SubscriptionChange) -> Subscription:
        return service.update_subscription(customer_id, change)

    @app.post("/customers/{customer_id}/subscription/cancel", response_model=Subscription)
    def cancel_subscription(customer_id: str, payload: CancelRequest) -> Subscription:
        return service.cancel_subscription(customer_id, payload.reason)

    @app.get("/orders/{order_id}", response_model=Order)
    def get_order(order_id: str) -> Order:
        return service.get_order(order_id)

    @app.post("/orders/{order_id}/refund", response_model=RefundResponse)
    def refund_order(order_id: str, payload: RefundRequest) -> RefundResponse:
        return service.refund_order(order_id, payload.amount, payload.reason, payload.issued_by)

    @app.get("/tickets")
    def list_tickets(status: str | None = None) -> list[dict]:
        return service.list_tickets(status)

    @app.post("/tickets", status_code=201)
    def create_ticket(payload: TicketCreate) -> dict:
        return service.create_ticket(payload)

    @app.get("/tickets/{ticket_id}")
    def get_ticket(ticket_id: str) -> dict:
        return service.get_ticket(ticket_id)

    @app.patch("/tickets/{ticket_id}")
    def patch_ticket(ticket_id: str, patch: TicketPatch) -> dict:
        return service.patch_ticket(ticket_id, patch)

    @app.get("/tickets/{ticket_id}/notes")
    def list_notes(ticket_id: str) -> list[dict]:
        return service.list_notes(ticket_id)

    @app.post("/tickets/{ticket_id}/notes", status_code=201)
    def add_note(ticket_id: str, payload: NoteCreate) -> dict:
        return service.add_note(ticket_id, payload.author, payload.body)

    @app.post("/tickets/{ticket_id}/escalate", status_code=201)
    def escalate(ticket_id: str, payload: EscalationCreate) -> dict:
        return service.escalate(ticket_id, payload)

    @app.get("/audit")
    def audit(limit: int = 200) -> list[dict]:
        return service.audit_log(limit)

    return app
