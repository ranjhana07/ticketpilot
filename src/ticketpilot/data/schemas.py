from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PRIORITIES = ("low", "normal", "high", "urgent")


@dataclass
class Ticket:
    ticket_id: str
    subject: str
    body: str
    from_email: str
    from_name: str = ""
    language: str = "en"
    channel: str = "email"
    created_at: str = ""
    intent: str | None = None
    priority: str | None = None
    entity: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return f"{self.subject}\n{self.body}".strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Ticket":
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in raw.items() if key in known})
