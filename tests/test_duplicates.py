from ticketpilot.data.schemas import Ticket
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.triage.duplicates import DuplicateDetector, entities_conflict, extract_entities


def make(ticket_id: str, body: str, email: str = "a@x.io") -> Ticket:
    return Ticket(ticket_id=ticket_id, subject="", body=body, from_email=email)


def test_entities_include_order_ids_and_sender():
    ticket = make("1", "refund ord-12345 please", "Maya@X.io")
    assert extract_entities(ticket) == {"ORD-12345", "maya@x.io"}


def test_conflict_when_identifiers_differ():
    assert entities_conflict(make("1", "ORD-11111 late", "a@x.io"), make("2", "ORD-22222 late", "b@x.io"))
    assert not entities_conflict(make("1", "ORD-11111 late"), make("2", "ORD-11111 still late"))


def test_guard_blocks_similar_text_with_other_order():
    detector = DuplicateDetector(HashingEmbedder(), threshold=0.5)
    left = make("1", "please refund order ORD-11111 now", "a@x.io")
    right = make("2", "please refund order ORD-22222 now", "b@x.io")
    assert detector.is_duplicate(left, right)[0] is False
    unguarded = DuplicateDetector(HashingEmbedder(), threshold=0.5, use_entity_guard=False)
    assert unguarded.is_duplicate(left, right)[0] is True


def test_find_returns_ranked_matches_and_skips_self():
    detector = DuplicateDetector(HashingEmbedder(), threshold=0.4)
    tickets = [
        make("1", "reset link expired, need a new password email", "a@x.io"),
        make("2", "my password reset link expired, please send a new one", "a@x.io"),
        make("3", "invoice for last quarter", "c@x.io"),
    ]
    detector.add(tickets)
    matches = detector.find(tickets[0])
    assert [m.ticket_id for m in matches] == ["2"]


def test_find_on_empty_index():
    assert DuplicateDetector(HashingEmbedder()).find(make("1", "hello")) == []
