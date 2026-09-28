from __future__ import annotations

from typing import Any

import httpx


class HelpdeskError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class HelpdeskClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8001", http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(base_url=base_url, timeout=15.0)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise HelpdeskError(response.status_code, str(detail))
        return response.json()

    def lookup_customer(self, email: str) -> dict:
        return self._request("GET", "/customers/lookup", params={"email": email})

    def get_customer(self, customer_id: str) -> dict:
        return self._request("GET", f"/customers/{customer_id}")

    def get_order(self, order_id: str) -> dict:
        return self._request("GET", f"/orders/{order_id}")

    def list_orders(self, customer_id: str) -> list[dict]:
        return self._request("GET", f"/customers/{customer_id}/orders")

    def verify_identity(self, customer_id: str, requester_email: str) -> dict:
        return self._request("POST", f"/customers/{customer_id}/verify", json={"requester_email": requester_email})

    def refund_order(self, order_id: str, amount: float, reason: str, issued_by: str = "agent") -> dict:
        return self._request(
            "POST", f"/orders/{order_id}/refund", json={"amount": amount, "reason": reason, "issued_by": issued_by}
        )

    def reset_password(self, customer_id: str) -> dict:
        return self._request("POST", f"/customers/{customer_id}/reset-password")

    def update_subscription(self, customer_id: str, plan: str, billing_cycle: str | None = None) -> dict:
        payload = {"plan": plan}
        if billing_cycle:
            payload["billing_cycle"] = billing_cycle
        return self._request("PUT", f"/customers/{customer_id}/subscription", json=payload)

    def cancel_subscription(self, customer_id: str, reason: str) -> dict:
        return self._request("POST", f"/customers/{customer_id}/subscription/cancel", json={"reason": reason})

    def add_note(self, ticket_id: str, body: str, author: str = "agent") -> dict:
        return self._request("POST", f"/tickets/{ticket_id}/notes", json={"author": author, "body": body})

    def escalate(self, ticket_id: str, team: str, reason: str) -> dict:
        return self._request("POST", f"/tickets/{ticket_id}/escalate", json={"team": team, "reason": reason})

    def create_ticket(self, payload: dict) -> dict:
        return self._request("POST", "/tickets", json=payload)

    def get_ticket(self, ticket_id: str) -> dict:
        return self._request("GET", f"/tickets/{ticket_id}")

    def list_tickets(self, status: str | None = None) -> list[dict]:
        return self._request("GET", "/tickets", params={"status": status} if status else None)

    def patch_ticket(self, ticket_id: str, **fields: Any) -> dict:
        return self._request("PATCH", f"/tickets/{ticket_id}", json=fields)

    def audit_log(self, limit: int = 200) -> list[dict]:
        return self._request("GET", "/audit", params={"limit": limit})
