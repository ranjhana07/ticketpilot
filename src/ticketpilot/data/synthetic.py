from __future__ import annotations

import random
from datetime import datetime, timedelta

from ticketpilot.data.schemas import PRIORITIES, Ticket
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


PRIORITY_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "security_report": (0.0, 0.1, 0.35, 0.55),
    "account_locked": (0.0, 0.15, 0.5, 0.35),
    "bug_report": (0.1, 0.45, 0.35, 0.1),
    "billing_refund": (0.05, 0.5, 0.35, 0.1),
    "password_reset": (0.05, 0.55, 0.3, 0.1),
    "cancel_subscription": (0.1, 0.6, 0.25, 0.05),
    "change_plan": (0.25, 0.6, 0.14, 0.01),
    "order_status": (0.1, 0.55, 0.3, 0.05),
    "invoice_request": (0.3, 0.55, 0.14, 0.01),
    "data_export": (0.2, 0.55, 0.2, 0.05),
    "feature_request": (0.7, 0.28, 0.02, 0.0),
    "general_question": (0.65, 0.33, 0.02, 0.0),
}

PRIORITY_CUES: dict[str, list[str]] = {
    "urgent": [
        "This is urgent, our whole team is blocked.",
        "Production is affected right now.",
        "We have a client presentation in an hour and need this fixed ASAP.",
        "Please treat this as an emergency.",
        "URGENT: we cannot work until this is sorted.",
    ],
    "high": [
        "This is blocking the team today.",
        "We need this resolved by end of day.",
        "It is getting frustrating, this is the second time I am writing in.",
        "Please look at this soon, it is holding up a release.",
    ],
    "normal": ["Thanks for looking into it.", "Let me know if you need anything else from me.", ""],
    "low": [
        "No rush on this.",
        "Whenever you get a chance is fine.",
        "Not urgent at all, just curious.",
        "Low priority, just wanted to ask.",
    ],
}

LABEL_NOISE = 0.06


def sample_priority(rng: random.Random, intent: str) -> str:
    return rng.choices(PRIORITIES, weights=PRIORITY_WEIGHTS[intent])[0]


def flip_priority(rng: random.Random, priority: str) -> str:
    position = PRIORITIES.index(priority)
    options = [index for index in (position - 1, position + 1) if 0 <= index < len(PRIORITIES)]
    return PRIORITIES[rng.choice(options)]


def make_ticket(rng: random.Random, index: int, intent: str | None = None) -> Ticket:
    intent = intent or rng.choice(INTENTS)
    cue_priority = sample_priority(rng, intent)
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    email = make_email(rng, first, last)
    order_id = make_order_id(rng)
    subject = rng.choice(SUBJECTS[intent]).format(order=order_id)
    body = render_core(rng, intent, order_id)
    cue = rng.choice(PRIORITY_CUES[cue_priority])
    if cue:
        body = f"{body} {cue}" if rng.random() < 0.7 else f"{cue} {body}"
    priority = flip_priority(rng, cue_priority) if rng.random() < LABEL_NOISE else cue_priority
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
        priority=priority,
        entity=entity,
    )


def generate_tickets(count: int, seed: int = 13) -> list[Ticket]:
    rng = random.Random(seed)
    return [make_ticket(rng, index) for index in range(count)]
