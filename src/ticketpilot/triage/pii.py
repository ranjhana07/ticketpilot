from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\w-])")


@dataclass(frozen=True)
class Span:
    label: str
    start: int
    end: int
    value: str


@dataclass
class Redaction:
    text: str
    spans: list[Span] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def labels(self) -> set[str]:
        return {span.label for span in self.spans}


@dataclass(frozen=True)
class Rule:
    label: str
    pattern: re.Pattern[str]
    validator: Callable[[str], bool] | None = None


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _plausible_phone(value: str) -> bool:
    return 9 <= len(_digits(value)) <= 15


RULES: list[Rule] = [
    Rule("EMAIL", EMAIL),
    Rule("PHONE", PHONE, _plausible_phone),
]


def find_spans(text: str, rules: list[Rule] | None = None) -> list[Span]:
    found: list[Span] = []
    for rule in rules or RULES:
        for match in rule.pattern.finditer(text):
            value = match.group(0)
            if rule.validator and not rule.validator(value):
                continue
            found.append(Span(rule.label, match.start(), match.end(), value))
    return resolve_overlaps(found)


def resolve_overlaps(spans: list[Span]) -> list[Span]:
    ordered = sorted(spans, key=lambda span: (span.start, -(span.end - span.start)))
    kept: list[Span] = []
    for span in ordered:
        if kept and span.start < kept[-1].end:
            continue
        kept.append(span)
    return kept


def redact(text: str) -> Redaction:
    spans = find_spans(text)
    counters: dict[str, int] = {}
    mapping: dict[str, str] = {}
    pieces: list[str] = []
    cursor = 0
    for span in spans:
        counters[span.label] = counters.get(span.label, 0) + 1
        token = f"[{span.label}_{counters[span.label]}]"
        mapping[token] = span.value
        pieces.append(text[cursor:span.start])
        pieces.append(token)
        cursor = span.end
    pieces.append(text[cursor:])
    return Redaction("".join(pieces), spans, mapping)


def restore(text: str, mapping: dict[str, str]) -> str:
    for token, value in mapping.items():
        text = text.replace(token, value)
    return text
