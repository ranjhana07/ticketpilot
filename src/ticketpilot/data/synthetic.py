from __future__ import annotations

import random
from datetime import datetime, timedelta

from ticketpilot.data.schemas import Ticket
from ticketpilot.data.templates import CORES_EN, INTENTS, ORDER_INTENTS, SUBJECTS

FIRST_NAMES = [
    "Maya", "Daniel", "Priya", "Lucas", "Hannah", "Omar", "Elena", "Tomas", "Aisha", "Ben",
    "Sofia", "Marcus", "Ines", "Kenji", "Olivia", "Rahul", "Greta", "Samir", "Nora", "Felix",
]
LAST_NAMES = [
    "Reed", "Okafor", "Lindqvist", "Moreau", "Patel", "Novak", "Silva", "Brandt", "Haddad", "Kim",
    "Walsh", "Rossi", "Tanaka", "Duarte", "Fischer", "Ibrahim", "Larsen", "Mendez", "Quinn", "Sato",
]
DOMAINS = [
    "brightfield.io", "northpeak.co", "tallpine.dev", "ledgerlane.com", "fernworks.net",
    "quillhouse.org", "stonebridge.co", "harborlight.io", "oakmere.com", "pixelmint.dev",
]
PLANS = ["Free", "Team", "Business"]
AMOUNTS = [9.0, 12.0, 24.0, 36.0, 49.0, 72.0, 96.0, 144.0, 180.0, 299.0]


def make_email(rng: random.Random, first: str, last: str) -> str:
    style = rng.choice(["{f}.{l}", "{f}{l}", "{f}_{l}", "{fi}{l}"])
    local = style.format(f=first.lower(), l=last.lower(), fi=first[0].lower())
    return f"{local}@{rng.choice(DOMAINS)}"


def make_order_id(rng: random.Random) -> str:
    return f"ORD-{rng.randint(10000, 99999)}"


def render_core(rng: random.Random, intent: str, order_id: str) -> str:
    template = rng.choice(CORES_EN[intent])
    return template.format(
        order=order_id,
        amount=f"${rng.choice(AMOUNTS):.2f}",
        plan=rng.choice(PLANS),
    )


def make_ticket(rng: random.Random, index: int, intent: str | None = None) -> Ticket:
    intent = intent or rng.choice(INTENTS)
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    email = make_email(rng, first, last)
    order_id = make_order_id(rng)
    subject = rng.choice(SUBJECTS[intent]).format(order=order_id)
    body = render_core(rng, intent, order_id)
    entity = order_id if intent in ORDER_INTENTS else email
    created = datetime(2026, 1, 1) + timedelta(minutes=rng.randint(0, 60 * 24 * 120))
    return Ticket(
        ticket_id=f"SYN-{index:06d}",
        subject=subject,
        body=body,
        from_email=email,
        from_name=f"{first} {last}",
        created_at=created.isoformat(timespec="minutes"),
        intent=intent,
        entity=entity,
    )


def generate_tickets(count: int, seed: int = 13) -> list[Ticket]:
    rng = random.Random(seed)
    return [make_ticket(rng, index) for index in range(count)]
