from __future__ import annotations

import csv
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


def load_tickets(path: Path | None = None) -> list[Ticket]:
    tickets = []
    for index, row in enumerate(load_rows(path)):
        tickets.append(
            Ticket(
                ticket_id=f"BTX-{index:05d}",
                subject="",
                body=row["instruction"].strip(),
                from_email="",
                intent=row["intent"],
                meta={"category": row["category"], "flags": row["flags"]},
            )
        )
    return tickets
