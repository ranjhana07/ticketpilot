from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ticketpilot.agent.client import HelpdeskError
from ticketpilot.agent.runner import RunResult
from ticketpilot.api.container import Container
from ticketpilot.data.schemas import PRIORITIES, Ticket

STATIC_DIR = Path(__file__).parent / "static"


class ApproveRequest(BaseModel):
    decisions: dict[str, Literal["approve", "reject"]]
    reviewer: str = "reviewer"


class DraftUpdate(BaseModel):
    reply: str = Field(min_length=1)


class SendRequest(BaseModel):
    reviewer: str = "reviewer"


def _ticket_from_raw(raw: dict[str, Any]) -> Ticket:
    return Ticket(
        ticket_id=raw["id"],
        subject=raw["subject"],
        body=raw["body"],
        from_email=raw["customer_email"],
        from_name=raw["customer_name"],
        channel=raw["channel"],
        created_at=raw["created_at"],
    )


def _priority_rank(raw: dict[str, Any]) -> int:
    triage = raw.get("triage") or {}
    priority = triage.get("priority")
    return PRIORITIES.index(priority) if priority in PRIORITIES else -1


def create_api(container: Container) -> FastAPI:
    helpdesk = container.helpdesk
    app = FastAPI(title="ticketpilot", version="0.1.0")

    @app.exception_handler(HelpdeskError)
    async def helpdesk_error(_: Request, error: HelpdeskError) -> JSONResponse:
        return JSONResponse(status_code=error.status, content={"detail": error.detail})

    def index_ticket(raw: dict[str, Any]) -> None:
        detector = container.triage.duplicate_detector if container.triage else None
        if detector is not None and raw["id"] not in container.indexed:
            detector.add([_ticket_from_raw(raw)])
            container.indexed.add(raw["id"])

    def triaged(raw: dict[str, Any]) -> dict[str, Any]:
        if container.triage is None:
            return raw
        if raw.get("triage"):
            index_ticket(raw)
            return raw
        result = container.triage.analyze(_ticket_from_raw(raw)).to_dict()
        status = "triaged" if raw["status"] == "new" else raw["status"]
        updated = helpdesk.patch_ticket(raw["id"], triage=result, status=status)
        index_ticket(raw)
        return updated

    def store(ticket_id: str, result: RunResult) -> dict[str, Any]:
        proposal = {
            "actions": result.actions,
            "pending_approvals": result.pending_approvals,
            "kb_hits": [
                {"article_id": hit["article_id"], "title": hit["title"], "heading": hit["heading"]}
                for hit in result.kb_hits
            ],
        }
        return helpdesk.patch_ticket(
            ticket_id,
            status=result.status,
            triage=result.triage or None,
            proposal=proposal,
            draft=result.draft,
            thread_id=result.thread_id,
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        settings = container.settings
        return {
            "llm_provider": settings.llm_provider,
            "model": settings.model if settings.llm_provider == "anthropic" else "scripted",
            "auto_refund_limit": settings.auto_refund_limit,
            "max_refund": settings.max_refund,
            "refund_window_days": settings.refund_window_days,
            "triage_loaded": container.triage is not None,
        }

    @app.get("/api/tickets")
    def list_tickets(status: str | None = None) -> list[dict[str, Any]]:
        with container.lock:
            tickets = [triaged(raw) for raw in helpdesk.list_tickets(status)]
        return sorted(tickets, key=lambda raw: (_priority_rank(raw), raw["created_at"]), reverse=True)

    @app.get("/api/tickets/{ticket_id}")
    def get_ticket(ticket_id: str) -> dict[str, Any]:
        with container.lock:
            raw = triaged(helpdesk.get_ticket(ticket_id))
        raw["notes"] = helpdesk.list_notes(ticket_id)
        return raw

    @app.post("/api/tickets/{ticket_id}/run")
    def run_agent(ticket_id: str) -> dict[str, Any]:
        raw = helpdesk.get_ticket(ticket_id)
        if raw["status"] in ("replied", "awaiting_approval"):
            raise HTTPException(status_code=409, detail=f"ticket is {raw['status']}")
        with container.lock:
            result = container.agent.start(_ticket_from_raw(raw))
            return store(ticket_id, result)

    @app.post("/api/tickets/{ticket_id}/approve")
    def approve(ticket_id: str, payload: ApproveRequest) -> dict[str, Any]:
        raw = helpdesk.get_ticket(ticket_id)
        if not raw.get("thread_id") or raw["status"] != "awaiting_approval":
            raise HTTPException(status_code=409, detail="ticket has no pending approval")
        with container.lock:
            try:
                result = container.agent.resume(raw["thread_id"], dict(payload.decisions), payload.reviewer)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=f"approval session expired, run the ticket again ({error})")
            return store(ticket_id, result)

    @app.put("/api/tickets/{ticket_id}/draft")
    def update_draft(ticket_id: str, payload: DraftUpdate) -> dict[str, Any]:
        raw = helpdesk.get_ticket(ticket_id)
        draft = dict(raw.get("draft") or {"citations": [], "needs_human_attention": False})
        draft.update(reply=payload.reply, edited=True)
        return helpdesk.patch_ticket(ticket_id, draft=draft)

    @app.post("/api/tickets/{ticket_id}/send")
    def send_reply(ticket_id: str, payload: SendRequest) -> dict[str, Any]:
        raw = helpdesk.get_ticket(ticket_id)
        if not raw.get("draft"):
            raise HTTPException(status_code=409, detail="no draft to send")
        if raw["status"] == "awaiting_approval":
            raise HTTPException(status_code=409, detail="resolve the pending approvals first")
        draft = dict(raw["draft"])
        draft["sent_by"] = payload.reviewer
        draft["sent_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        helpdesk.add_note(ticket_id, f"reply sent by {payload.reviewer}", author=payload.reviewer)
        return helpdesk.patch_ticket(ticket_id, status="replied", draft=draft)

    @app.get("/api/audit")
    def audit(limit: int = 100) -> list[dict[str, Any]]:
        return helpdesk.audit_log(limit)

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
    return app
