from collections import Counter

from ticketpilot.data.io import read_tickets, write_tickets
from ticketpilot.data.splits import stratified_split, subsample_per_class
from ticketpilot.data.synthetic import generate_tickets, luhn_card
from ticketpilot.data.templates import INTENTS


def test_generation_is_deterministic():
    first = generate_tickets(30, seed=5)
    second = generate_tickets(30, seed=5)
    assert [t.body for t in first] == [t.body for t in second]


def test_every_intent_appears_and_labels_are_valid():
    tickets = generate_tickets(600, seed=1)
    assert set(t.intent for t in tickets) == set(INTENTS)
    assert set(t.priority for t in tickets) <= {"low", "normal", "high", "urgent"}


def test_order_intents_carry_order_id_entity():
    tickets = generate_tickets(200, seed=2)
    for ticket in tickets:
        if ticket.intent in ("billing_refund", "order_status"):
            assert ticket.entity.startswith("ORD-")
        if ticket.intent == "password_reset":
            assert ticket.entity == ticket.from_email


def test_foreign_share_produces_other_languages():
    tickets = generate_tickets(200, seed=3, foreign_share=0.5)
    assert {t.language for t in tickets} >= {"en", "es", "fr", "de"}


def test_luhn_card_is_valid():
    import random

    number = luhn_card(random.Random(9))
    total = 0
    for position, char in enumerate(reversed(number)):
        digit = int(char)
        if position % 2 == 1:
            digit *= 2
            digit -= 9 if digit > 9 else 0
        total += digit
    assert total % 10 == 0


def test_jsonl_roundtrip(tmp_path):
    tickets = generate_tickets(10, seed=4)
    path = tmp_path / "tickets.jsonl"
    assert write_tickets(tickets, path) == 10
    assert read_tickets(path) == tickets


def test_stratified_split_keeps_classes():
    tickets = generate_tickets(400, seed=6)
    train, test = stratified_split(tickets, key=lambda t: t.intent, test_size=0.25)
    assert len(train) + len(test) == 400
    assert Counter(t.intent for t in test).keys() == Counter(t.intent for t in tickets).keys()


def test_subsample_per_class_caps_counts():
    tickets = generate_tickets(500, seed=7)
    sample = subsample_per_class(tickets, key=lambda t: t.intent, per_class=10)
    assert max(Counter(t.intent for t in sample).values()) == 10


def test_duplicate_pairs_have_expected_structure():
    from ticketpilot.data.synthetic import make_duplicate_pairs

    pairs = make_duplicate_pairs(90, seed=8)
    positives = [(a, b) for a, b, label in pairs if label]
    assert len(positives) == 30
    for a, b in positives:
        assert a.intent == b.intent and a.entity == b.entity and a.from_email == b.from_email
    for a, b, label in pairs:
        if not label:
            assert a.entity != b.entity
