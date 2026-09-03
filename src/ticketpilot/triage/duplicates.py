from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from ticketpilot.data.schemas import Ticket
from ticketpilot.embeddings import Embedder
from ticketpilot.triage.pii import EMAIL

ORDER_ID = re.compile(r"\bORD-\d{4,8}\b", re.IGNORECASE)


def extract_entities(ticket: Ticket) -> set[str]:
    found = {match.upper() for match in ORDER_ID.findall(ticket.text)}
    if ticket.from_email:
        found.add(ticket.from_email.lower())
    return found


def entities_conflict(left: Ticket, right: Ticket) -> bool:
    a, b = extract_entities(left), extract_entities(right)
    return bool(a) and bool(b) and a.isdisjoint(b)


@dataclass(frozen=True)
class DuplicateMatch:
    ticket_id: str
    score: float


@dataclass
class DuplicateDetector:
    embedder: Embedder
    threshold: float = 0.8
    use_entity_guard: bool = True
    _tickets: list[Ticket] = field(default_factory=list)
    _vectors: np.ndarray | None = None

    def add(self, tickets: list[Ticket]) -> None:
        if not tickets:
            return
        vectors = self.embedder.encode([ticket.text for ticket in tickets])
        self._tickets.extend(tickets)
        self._vectors = vectors if self._vectors is None else np.vstack([self._vectors, vectors])

    def similarity(self, left: Ticket, right: Ticket) -> float:
        a, b = self.embedder.encode([left.text, right.text])
        return float(a @ b)

    def is_duplicate(self, left: Ticket, right: Ticket) -> tuple[bool, float]:
        score = self.similarity(left, right)
        if self.use_entity_guard and entities_conflict(left, right):
            return False, score
        return score >= self.threshold, score

    def find(self, ticket: Ticket, top_k: int = 3) -> list[DuplicateMatch]:
        if self._vectors is None:
            return []
        query = self.embedder.encode([ticket.text])[0]
        scores = self._vectors @ query
        matches = []
        for position in np.argsort(-scores)[: top_k * 3]:
            candidate = self._tickets[int(position)]
            if candidate.ticket_id == ticket.ticket_id:
                continue
            if scores[position] < self.threshold:
                break
            if self.use_entity_guard and entities_conflict(ticket, candidate):
                continue
            matches.append(DuplicateMatch(candidate.ticket_id, round(float(scores[position]), 4)))
            if len(matches) == top_k:
                break
        return matches
