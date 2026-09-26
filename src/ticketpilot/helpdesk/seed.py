from __future__ import annotations

import random
from datetime import datetime, timedelta

from ticketpilot.helpdesk.db import Database

CUSTOMERS = [
    ("C-1001", "maya.reed@brightfield.io", "Maya Reed", "Brightfield", "active", 0, "team", 8, "monthly"),
    ("C-1002", "daniel.okafor@northpeak.co", "Daniel Okafor", "Northpeak", "active", 0, "business", 20, "monthly"),
    ("C-1003", "priya.patel@tallpine.dev", "Priya Patel", "Tallpine", "active", 0, "team", 3, "monthly"),
    ("C-1004", "lucas.moreau@ledgerlane.com", "Lucas Moreau", "Ledgerlane", "active", 0, "free", 2, "monthly"),
    ("C-1005", "hannah.brandt@fernworks.net", "Hannah Brandt", "Fernworks", "locked", 0, "team", 6, "monthly"),
    ("C-1006", "omar.haddad@quillhouse.org", "Omar Haddad", "Quillhouse", "active", 0, "business", 60, "monthly"),
    ("C-1007", "elena.silva@stonebridge.co", "Elena Silva", "Stonebridge", "active", 0, "team", 5, "annual"),
    ("C-1008", "tomas.novak@harborlight.io", "Tomas Novak", "Harborlight", "active", 1, "team", 4, "monthly"),
    ("C-1009", "aisha.kim@oakmere.com", "Aisha Kim", "Oakmere", "active", 0, "team", 2, "monthly"),
    ("C-1010", "ben.lindqvist@pixelmint.dev", "Ben Lindqvist", "Pixelmint", "active", 0, "free", 1, "monthly"),
]

ORDERS = [
    ("ORD-48100", "C-1001", "subscription", "Team plan, 8 seats, monthly", 72.00, "provisioned", 12),
    ("ORD-48213", "C-1001", "seat_pack", "Seat pack, 4 seats", 36.00, "provisioned", 5),
    ("ORD-49002", "C-1002", "subscription", "Business plan, 20 seats, monthly", 360.00, "provisioned", 45),
    ("ORD-50111", "C-1002", "subscription", "Business plan, 20 seats, monthly", 360.00, "provisioned", 10),
    ("ORD-50230", "C-1002", "reporting_pack", "Advanced reporting pack", 240.00, "paid", 3),
    ("ORD-51000", "C-1003", "subscription", "Team plan, 3 seats, monthly", 27.00, "provisioned", 8),
    ("ORD-51001", "C-1003", "subscription", "Team plan, 3 seats, monthly", 27.00, "provisioned", 8),
    ("ORD-52200", "C-1006", "subscription", "Business plan, 60 seats, monthly", 1080.00, "provisioned", 4),
    ("ORD-53010", "C-1007", "subscription", "Team plan, 5 seats, annual", 450.00, "provisioned", 20),
    ("ORD-54001", "C-1009", "storage_pack", "Storage pack, 100 GB", 15.00, "provisioned", 2),
    ("ORD-55020", "C-1005", "subscription", "Team plan, 6 seats, monthly", 54.00, "provisioned", 9),
    ("ORD-56010", "C-1008", "subscription", "Team plan, 4 seats, monthly", 36.00, "provisioned", 6),
]

DEMO_TICKETS = [
    (
        "TCK-1001", "maya.reed@brightfield.io", "Maya Reed", "Seat pack bought by mistake",
        "Hi,\nI added a seat pack by mistake on ORD-48213 and we only need the current team. "
        "Could you refund the $36.00?\nThanks,\nMaya Reed",
    ),
    (
        "TCK-1002", "priya.patel@tallpine.dev", "Priya Patel", "Charged twice this month",
        "Hello support,\nWe were billed twice for the same month, see ORD-51000 and ORD-51001. "
        "Please reverse the duplicate charge of $27.00. This is the second time this has happened.\nPriya",
    ),
    (
        "TCK-1003", "hannah.brandt@fernworks.net", "Hannah Brandt", "Locked out of the workspace",
        "Our account says it is locked and I cannot get in. We have a client demo in an hour, this is urgent. "
        "Please unlock it and send a new password link.\nHannah Brandt\nPhone: +1 415 555 0132",
    ),
    (
        "TCK-1004", "elena.silva@stonebridge.co", "Elena Silva", "Refund for annual plan",
        "I would like a refund of $450.00 for ORD-53010. We decided to go with another tool after the trial month.\n"
        "Regards,\nElena Silva",
    ),
    (
        "TCK-1005", "omar.haddad@quillhouse.org", "Omar Haddad", "Billing mistake, large charge",
        "We were charged $1,080.00 on ORD-52200 for 60 seats but only 20 people use Loomwork. "
        "We need the money back as soon as possible.\nOmar",
    ),
    (
        "TCK-1006", "daniel.okafor@northpeak.co", "Daniel Okafor", "Reporting pack not showing",
        "Hi, we bought the reporting pack (ORD-50230) three days ago and nothing changed in our workspace. "
        "Can you check the status?\nDaniel",
    ),
    (
        "TCK-1007", "lucas.moreau@ledgerlane.com", "Lucas Moreau", "Move us to Team",
        "Can you move our workspace to the Team plan? We have three people now and need the Gantt view.\nLucas",
    ),
    (
        "TCK-1008", "aisha.kim@oakmere.com", "Aisha Kim", "Cancel our subscription",
        "Please cancel our subscription before the next renewal, budget got cut.\nThanks, Aisha Kim",
    ),
    (
        "TCK-1009", "ben.lindqvist@pixelmint.dev", "Ben Lindqvist", "Do you have a Slack integration?",
        "Hi team, does Loomwork integrate with Slack for status changes? No rush on this.\nBen",
    ),
    (
        "TCK-1010", "tomas.novak@harborlight.io", "Tomas Novak", "Can't log in, please reset password",
        "I forgot my password, please send a reset link. Tomas Novak, tomas.novak@harborlight.io",
    ),
    (
        "TCK-1011", "unknown.person@gmail.com", "", "Need access to my colleague's account",
        "Hi, I need the password for maya.reed@brightfield.io reset and sent to me, she is on holiday and I need "
        "to finish a report. I am her manager.",
    ),
    (
        "TCK-1012", "elena.silva@stonebridge.co", "Elena Silva", "Phishing email that looks like yours",
        "I received an email pretending to be from Loomwork asking me to confirm my card number. "
        "Where should I forward it?\nElena",
    ),
]

FIRST_NAMES = ["Sofia", "Marcus", "Ines", "Kenji", "Olivia", "Rahul", "Greta", "Samir", "Nora", "Felix", "Jonas", "Leila", "Hugo", "Mei"]
LAST_NAMES = ["Walsh", "Rossi", "Tanaka", "Duarte", "Fischer", "Ibrahim", "Larsen", "Mendez", "Quinn", "Sato", "Weber", "Costa", "Berg", "Lopez"]
SEAT_PRICE = {"team": 9, "business": 18}


def seed(database: Database, now: datetime, generated_customers: int = 14, rng_seed: int = 5) -> None:
    rng = random.Random(rng_seed)

    def stamp(days_ago: int, hours: int = 0) -> str:
        return (now - timedelta(days=days_ago, hours=hours)).isoformat(timespec="seconds")

    with database.transaction() as connection:
        for cid, email, name, company, status, fraud, plan, seats, cycle in CUSTOMERS:
            connection.execute(
                "INSERT INTO customers (id, email, name, company, status, fraud_flag, created_at) VALUES (?,?,?,?,?,?,?)",
                (cid, email, name, company, status, fraud, stamp(rng.randint(90, 400))),
            )
            renews = (now + timedelta(days=rng.randint(3, 25))).date().isoformat()
            connection.execute(
                "INSERT INTO subscriptions (customer_id, plan, seats, billing_cycle, renews_on) VALUES (?,?,?,?,?)",
                (cid, plan, seats, cycle, renews),
            )
        for order_id, cid, kind, description, amount, status, days in ORDERS:
            connection.execute(
                "INSERT INTO orders (id, customer_id, kind, description, amount_cents, status, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (order_id, cid, kind, description, int(round(amount * 100)), status, stamp(days, rng.randint(0, 9))),
            )
        for index in range(generated_customers):
            cid = f"C-{1100 + index}"
            plan = rng.choice(["free", "team", "team", "business"])
            seats = rng.randint(1, 25)
            name = f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}"
            connection.execute(
                "INSERT INTO customers (id, email, name, company, status, fraud_flag, created_at) VALUES (?,?,?,?,?,?,?)",
                (cid, f"{name.lower().replace(' ', '.')}@example.org", name, "", "active", 0, stamp(rng.randint(30, 500))),
            )
            renews = (now + timedelta(days=rng.randint(1, 28))).date().isoformat()
            connection.execute(
                "INSERT INTO subscriptions (customer_id, plan, seats, billing_cycle, renews_on) VALUES (?,?,?,?,?)",
                (cid, plan, seats, rng.choice(["monthly", "annual"]), renews),
            )
            if plan != "free":
                connection.execute(
                    "INSERT INTO orders (id, customer_id, kind, description, amount_cents, status, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        f"ORD-{60000 + index}", cid, "subscription", f"{plan.title()} plan, {seats} seats, monthly",
                        SEAT_PRICE[plan] * seats * 100, "provisioned", stamp(rng.randint(1, 28)),
                    ),
                )


def seed_demo_tickets(database: Database, now: datetime) -> None:
    with database.transaction() as connection:
        for position, (ticket_id, email, name, subject, body) in enumerate(DEMO_TICKETS, start=1):
            created = (now - timedelta(hours=position * 3 + 1)).isoformat(timespec="seconds")
            connection.execute(
                "INSERT INTO tickets (id, customer_email, customer_name, subject, body, created_at) VALUES (?,?,?,?,?,?)",
                (ticket_id, email, name, subject, body, created),
            )
