from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ticketpilot.data.schemas import Ticket


def write_tickets(tickets: Iterable[Ticket], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for ticket in tickets:
            handle.write(json.dumps(ticket.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_tickets(path: Path) -> list[Ticket]:
    with path.open(encoding="utf-8") as handle:
        return [Ticket.from_dict(json.loads(line)) for line in handle if line.strip()]
