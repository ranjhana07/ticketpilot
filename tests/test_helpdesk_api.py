def test_lookup_is_case_insensitive_and_includes_subscription(helpdesk):
    response = helpdesk.get("/customers/lookup", params={"email": "Maya.Reed@Brightfield.io"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "C-1001"
    assert body["subscription"]["plan"] == "team"


def test_unknown_customer_is_404(helpdesk):
    assert helpdesk.get("/customers/lookup", params={"email": "nobody@example.com"}).status_code == 404
    assert helpdesk.get("/customers/C-9999").status_code == 404


def test_verify_matches_sender_email(helpdesk):
    good = helpdesk.post("/customers/C-1001/verify", json={"requester_email": "maya.reed@brightfield.io"})
    bad = helpdesk.post("/customers/C-1001/verify", json={"requester_email": "someone@else.com"})
    assert good.json()["verified"] is True
    assert bad.json()["verified"] is False


def test_orders_for_customer(helpdesk):
    orders = helpdesk.get("/customers/C-1002/orders").json()
    assert {o["id"] for o in orders} == {"ORD-49002", "ORD-50111", "ORD-50230"}


def test_refund_partial_then_balance_check(helpdesk):
    first = helpdesk.post("/orders/ORD-51000/refund", json={"amount": 10, "reason": "duplicate charge"})
    assert first.status_code == 200
    assert first.json()["order_refunded_total"] == 10.0
    too_much = helpdesk.post("/orders/ORD-51000/refund", json={"amount": 20, "reason": "duplicate charge"})
    assert too_much.status_code == 409
    assert "refundable balance" in too_much.json()["detail"]


def test_full_refund_marks_order_refunded_and_blocks_second(helpdesk):
    assert helpdesk.post("/orders/ORD-54001/refund", json={"amount": 15, "reason": "bought by mistake"}).json()["status"] == "refunded"
    again = helpdesk.post("/orders/ORD-54001/refund", json={"amount": 1, "reason": "bought by mistake"})
    assert again.status_code == 409


def test_refund_validation(helpdesk):
    assert helpdesk.post("/orders/ORD-54001/refund", json={"amount": 0, "reason": "none"}).status_code == 422
    assert helpdesk.post("/orders/ORD-00000/refund", json={"amount": 5, "reason": "missing"}).status_code == 404


def test_password_reset_unlocks_locked_account(helpdesk):
    assert helpdesk.get("/customers/C-1005").json()["status"] == "locked"
    response = helpdesk.post("/customers/C-1005/reset-password")
    assert response.json() == {"status": "sent", "sent_to": "hannah.brandt@fernworks.net"}
    assert helpdesk.get("/customers/C-1005").json()["status"] == "active"


def test_flagged_account_cannot_be_reset(helpdesk):
    response = helpdesk.post("/customers/C-1008/reset-password")
    assert response.status_code == 403


def test_subscription_update_and_enterprise_block(helpdesk):
    updated = helpdesk.put("/customers/C-1004/subscription", json={"plan": "team", "billing_cycle": "annual"})
    assert updated.status_code == 200
    assert updated.json()["plan"] == "team" and updated.json()["billing_cycle"] == "annual"
    assert helpdesk.put("/customers/C-1004/subscription", json={"plan": "enterprise"}).status_code == 403


def test_cancel_marks_cancel_at_period_end(helpdesk):
    response = helpdesk.post("/customers/C-1009/subscription/cancel", json={"reason": "budget cut"})
    assert response.status_code == 200
    assert response.json()["cancel_at_period_end"] is True


def test_ticket_lifecycle_notes_and_escalation(helpdesk):
    created = helpdesk.post(
        "/tickets",
        json={"customer_email": "maya.reed@brightfield.io", "subject": "Hello", "body": "Testing"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    note = helpdesk.post(f"/tickets/{ticket_id}/notes", json={"body": "looked at billing"})
    assert note.status_code == 201
    assert len(helpdesk.get(f"/tickets/{ticket_id}/notes").json()) == 1
    escalated = helpdesk.post(f"/tickets/{ticket_id}/escalate", json={"team": "billing", "reason": "needs review"})
    assert escalated.json()["status"] == "escalated"
    assert helpdesk.get(f"/tickets/{ticket_id}").json()["status"] == "escalated"


def test_patch_ticket_stores_json_fields(helpdesk):
    patched = helpdesk.patch("/tickets/TCK-1001", json={"status": "triaged", "triage": {"intent": "billing_refund"}})
    assert patched.json()["status"] == "triaged"
    assert patched.json()["triage"] == {"intent": "billing_refund"}


def test_duplicate_ticket_id_conflicts(helpdesk):
    payload = {"id": "TCK-1001", "customer_email": "a@b.c", "subject": "x", "body": "y"}
    assert helpdesk.post("/tickets", json=payload).status_code == 409


def test_audit_log_records_actions(helpdesk):
    helpdesk.post("/orders/ORD-54001/refund", json={"amount": 5, "reason": "partial refund", "issued_by": "agent"})
    entries = helpdesk.get("/audit").json()
    assert entries[0]["action"] == "refund_order"
    assert entries[0]["detail"]["amount"] == 5.0
