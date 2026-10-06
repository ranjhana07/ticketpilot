def test_health_and_config(inbox):
    assert inbox.get("/api/health").json() == {"status": "ok"}
    config = inbox.get("/api/config").json()
    assert config["llm_provider"] == "scripted"
    assert config["auto_refund_limit"] == 50.0 and config["triage_loaded"] is True


def test_queue_is_triaged_and_sorted_by_priority(inbox):
    tickets = inbox.get("/api/tickets").json()
    assert len(tickets) == 12
    assert all(t["triage"]["intent"] and t["triage"]["priority"] for t in tickets)
    ranks = ["low", "normal", "high", "urgent"]
    order = [ranks.index(t["triage"]["priority"]) for t in tickets]
    assert order == sorted(order, reverse=True)
    assert all(t["status"] == "triaged" for t in tickets)


def test_triage_redacts_pii_before_storing(inbox):
    ticket = inbox.get("/api/tickets/TCK-1003").json()
    assert "PHONE" in ticket["triage"]["pii_labels"]
    assert "555 0132" not in ticket["triage"]["redacted_text"]


def test_run_agent_stores_proposal_and_draft(inbox):
    ticket = inbox.post("/api/tickets/TCK-1001/run").json()
    assert ticket["status"] == "awaiting_review"
    assert [a["tool"] for a in ticket["proposal"]["actions"]] == ["lookup_customer", "verify_identity", "get_order", "refund_order"]
    assert ticket["draft"]["citations"] == ["refund-policy"]
    assert ticket["thread_id"]


def test_approval_flow_end_to_end(inbox, helpdesk):
    paused = inbox.post("/api/tickets/TCK-1004/run").json()
    assert paused["status"] == "awaiting_approval"
    pending = paused["proposal"]["pending_approvals"][0]
    assert pending["tool"] == "refund_order" and pending["args"]["amount"] == 450.0
    blocked_send = inbox.post("/api/tickets/TCK-1004/send", json={"reviewer": "sam"})
    assert blocked_send.status_code == 409
    done = inbox.post(
        "/api/tickets/TCK-1004/approve",
        json={"decisions": {pending["call_id"]: "approve"}, "reviewer": "sam"},
    ).json()
    assert done["status"] == "awaiting_review"
    assert done["proposal"]["pending_approvals"] == []
    assert helpdesk.get("/orders/ORD-53010").json()["refunded"] == 450.0


def test_approve_without_pending_request_conflicts(inbox):
    inbox.post("/api/tickets/TCK-1001/run")
    response = inbox.post("/api/tickets/TCK-1001/approve", json={"decisions": {}, "reviewer": "sam"})
    assert response.status_code == 409


def test_invalid_decision_value_is_rejected(inbox):
    response = inbox.post("/api/tickets/TCK-1004/approve", json={"decisions": {"x": "maybe"}})
    assert response.status_code == 422


def test_edit_and_send_draft(inbox):
    inbox.post("/api/tickets/TCK-1009/run")
    edited = inbox.put("/api/tickets/TCK-1009/draft", json={"reply": "Hi Ben, yes, there is a Slack integration."}).json()
    assert edited["draft"]["edited"] is True
    assert edited["draft"]["reply"].startswith("Hi Ben, yes")
    sent = inbox.post("/api/tickets/TCK-1009/send", json={"reviewer": "sam"}).json()
    assert sent["status"] == "replied" and sent["draft"]["sent_by"] == "sam"
    notes = inbox.get("/api/tickets/TCK-1009").json()["notes"]
    assert notes[-1]["body"] == "reply sent by sam"
    assert inbox.post("/api/tickets/TCK-1009/run").status_code == 409


def test_send_without_draft_conflicts(inbox):
    assert inbox.post("/api/tickets/TCK-1002/send", json={"reviewer": "sam"}).status_code == 409


def test_empty_draft_is_rejected(inbox):
    assert inbox.put("/api/tickets/TCK-1002/draft", json={"reply": ""}).status_code == 422


def test_unknown_ticket_is_404(inbox):
    assert inbox.get("/api/tickets/TCK-9999").status_code == 404
    assert inbox.post("/api/tickets/TCK-9999/run").status_code == 404


def test_audit_trail_lists_agent_actions(inbox):
    inbox.post("/api/tickets/TCK-1001/run")
    actions = [entry["action"] for entry in inbox.get("/api/audit").json()]
    assert "refund_order" in actions and "verify_identity" in actions
