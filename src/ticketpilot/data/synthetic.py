from __future__ import annotations

import random
from datetime import datetime, timedelta

from ticketpilot.data.schemas import PRIORITIES, Ticket
from ticketpilot.data.templates import CORES_EN, CORES_FOREIGN, INTENTS, ORDER_INTENTS, SUBJECTS

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


def render_core(rng: random.Random, intent: str, order_id: str, language: str = "en") -> str:
    pool = CORES_EN[intent] if language == "en" else CORES_FOREIGN[language][intent]
    template = rng.choice(pool)
    return template.format(
        order=order_id,
        amount=f"${rng.choice(AMOUNTS):.2f}",
        plan=rng.choice(PLANS),
    )


def luhn_card(rng: random.Random, prefix: str = "4") -> str:
    digits = [int(char) for char in prefix] + [rng.randint(0, 9) for _ in range(15 - len(prefix))]
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check = (10 - total % 10) % 10
    return "".join(str(digit) for digit in digits) + str(check)


def make_phone(rng: random.Random) -> str:
    area, mid, last = rng.randint(201, 989), rng.randint(200, 999), rng.randint(1000, 9999)
    return rng.choice([f"+1 {area} {mid} {last}", f"({area}) {mid}-{last}", f"+44 7{rng.randint(100, 999)} {rng.randint(100000, 999999)}"])


def make_signature(rng: random.Random, name: str, email: str, intent: str) -> str:
    lines = [name]
    if rng.random() < 0.4:
        lines.append(email)
    if rng.random() < 0.3:
        lines.append(f"Phone: {make_phone(rng)}")
    if intent in ("billing_refund", "invoice_request") and rng.random() < 0.25:
        card = luhn_card(rng)
        lines.append(rng.choice([f"Card on file ends in {card[-4:]}", f"Card used: {card[:4]} {card[4:8]} {card[8:12]} {card[12:]}"]))
    if intent == "security_report" and rng.random() < 0.5:
        lines.append(f"Seen from IP 203.0.113.{rng.randint(2, 250)}")
    return "\n".join(lines)


def compose_message(rng: random.Random, core: str, name: str, email: str, intent: str) -> str:
    parts = [rng.choice(GREETINGS), core, rng.choice(CLOSINGS)]
    message = "\n".join(part for part in parts if part)
    if rng.random() < 0.55:
        message = f"{message}\n{make_signature(rng, name, email, intent)}"
    return message


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


GREETINGS = ["Hi,", "Hello,", "Hi team,", "Hey,", "Good morning,", "Hello support,", "", ""]
CLOSINGS = ["Thanks,", "Regards,", "Best,", "Thank you!", "Cheers,", "", ""]


def add_typos(rng: random.Random, text: str, rate: float = 0.03) -> str:
    words = text.split(" ")
    for position, word in enumerate(words):
        if len(word) < 4 or rng.random() > rate:
            continue
        cut = rng.randint(1, len(word) - 2)
        if rng.random() < 0.5:
            words[position] = word[:cut] + word[cut + 1] + word[cut] + word[cut + 2:]
        else:
            words[position] = word[:cut] + word[cut + 1:]
    return " ".join(words)


def distractor(rng: random.Random, intent: str, order_id: str) -> str:
    other = rng.choice([name for name in INTENTS if name != intent])
    sentence = render_core(rng, other, order_id)
    return "Also, " + sentence[0].lower() + sentence[1:]


def make_ticket(
    rng: random.Random,
    index: int,
    intent: str | None = None,
    language: str = "en",
) -> Ticket:
    intent = intent or rng.choice(INTENTS)
    cue_priority = sample_priority(rng, intent)
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    email = make_email(rng, first, last)
    order_id = make_order_id(rng)
    subject = rng.choice(SUBJECTS[intent]).format(order=order_id)
    body = render_core(rng, intent, order_id, language)
    cue = rng.choice(PRIORITY_CUES[cue_priority]) if language == "en" else ""
    if cue:
        body = f"{body} {cue}" if rng.random() < 0.7 else f"{cue} {body}"
    if language == "en" and rng.random() < 0.15:
        body = f"{body} {distractor(rng, intent, order_id)}"
    if rng.random() < 0.35:
        body = add_typos(rng, body)
    if rng.random() < 0.12:
        body = body.lower()
    body = compose_message(rng, body, f"{first} {last}", email, intent)
    priority = flip_priority(rng, cue_priority) if rng.random() < LABEL_NOISE else cue_priority
    entity = order_id if intent in ORDER_INTENTS else email
    created = datetime(2026, 1, 1) + timedelta(minutes=rng.randint(0, 60 * 24 * 120))
    return Ticket(
        ticket_id=f"SYN-{index:06d}",
        subject=subject,
        body=body,
        from_email=email,
        from_name=f"{first} {last}",
        language=language,
        created_at=created.isoformat(timespec="minutes"),
        intent=intent,
        priority=priority,
        entity=entity,
    )


def generate_tickets(count: int, seed: int = 13, foreign_share: float = 0.0) -> list[Ticket]:
    rng = random.Random(seed)
    tickets = []
    for index in range(count):
        language = rng.choice(list(CORES_FOREIGN)) if rng.random() < foreign_share else "en"
        tickets.append(make_ticket(rng, index, language=language))
    return tickets
