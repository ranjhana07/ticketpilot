from __future__ import annotations

import csv
import random
import re
import urllib.request
from pathlib import Path

from ticketpilot.config import get_settings
from ticketpilot.data.schemas import Ticket

BITEXT_URL = (
    "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/"
    "resolve/main/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
)
BITEXT_FILENAME = "bitext_customer_support.csv"


def default_path() -> Path:
    return get_settings().data_dir / BITEXT_FILENAME


def download(path: Path | None = None, url: str = BITEXT_URL, force: bool = False) -> Path:
    target = path or default_path()
    if target.exists() and not force:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
        while chunk := response.read(1 << 16):
            handle.write(chunk)
    partial.replace(target)
    return target


def load_rows(path: Path | None = None) -> list[dict[str, str]]:
    source = path or default_path()
    if not source.exists():
        raise FileNotFoundError(f"{source} not found, run `ticketpilot data download` first")
    with source.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


PLACEHOLDER = re.compile(r"\{\{([^}]*)\}\}")

_FIRST_NAMES = ["Maya", "Daniel", "Priya", "Lucas", "Hannah", "Omar", "Elena", "Tomas", "Aisha", "Ben"]
_LAST_NAMES = ["Reed", "Okafor", "Lindqvist", "Moreau", "Patel", "Novak", "Silva", "Brandt", "Haddad", "Kim"]
_CITIES = ["Austin", "Leeds", "Rotterdam", "Lyon", "Toronto", "Pune", "Melbourne", "Seattle"]
_COUNTRIES = ["Canada", "Germany", "India", "France", "Australia", "Spain", "Ireland"]
_ACCOUNT_TYPES = ["personal", "business", "premium", "basic"]


def fill_placeholders(text: str, rng: random.Random) -> str:
    fillers = {
        "Order Number": lambda: str(rng.randint(10000, 99999)),
        "Invoice Number": lambda: f"INV-{rng.randint(1000, 9999)}",
        "Person Name": lambda: f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
        "Refund Amount": lambda: str(rng.choice([12, 25, 40, 59, 120, 249])),
        "Currency Symbol": lambda: rng.choice(["$", "EUR ", "GBP "]),
        "Delivery City": lambda: rng.choice(_CITIES),
        "Delivery Country": lambda: rng.choice(_COUNTRIES),
        "Account Type": lambda: rng.choice(_ACCOUNT_TYPES),
        "Account Category": lambda: rng.choice(_ACCOUNT_TYPES),
    }

    def replace(match: re.Match[str]) -> str:
        filler = fillers.get(match.group(1).strip())
        return filler() if filler else ""

    return PLACEHOLDER.sub(replace, text)


def load_tickets(path: Path | None = None, seed: int = 7, fill: bool = True) -> list[Ticket]:
    rng = random.Random(seed)
    tickets = []
    for index, row in enumerate(load_rows(path)):
        body = row["instruction"].strip()
        if fill:
            body = fill_placeholders(body, rng)
        tickets.append(
            Ticket(
                ticket_id=f"BTX-{index:05d}",
                subject="",
                body=body,
                from_email="",
                intent=row["intent"],
                meta={"category": row["category"], "flags": row["flags"]},
            )
        )
    return tickets
