from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
IPV4 = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
SECRET = re.compile(r"\b(?:sk_(?:live|test)_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9-]{20,})\b")
NAME_INTRO = re.compile(r"(?i:\b(?:my name is|this is|i am|i'm|name:)\s+)([A-Z][a-z]+(?:\s[A-Z][a-z'-]+){0,2})")
SIGN_OFF_NAME = re.compile(
    r"(?im:^(?:thanks|thank you|regards|best|best regards|kind regards|cheers|sincerely)[,!.]?[ \t]*\n)"
    r"([A-Z][a-z]+(?: [A-Z][a-z'-]+){1,2})[ \t]*$",
    re.MULTILINE,
)
SIGNATURE_LINE = re.compile(r"(?<=\n)([A-Z][a-z]+(?: [A-Z][a-z'-]+){1,2})[ \t]*$", re.MULTILINE)
STREET = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd)\b\.?"
)
PHONE = re.compile(r"(?<![\w-])(?<!\d[\s.-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\w-]|[\s.-]\d)")


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
    group: int = 0


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def luhn_valid(value: str) -> bool:
    digits = [int(char) for char in _digits(value)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def iban_valid(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    if not 15 <= len(compact) <= 34:
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(int(char, 36)) for char in rearranged)
    return int(numeric) % 97 == 1


def _plausible_phone(value: str) -> bool:
    return 9 <= len(_digits(value)) <= 15


RULES: list[Rule] = [
    Rule("EMAIL", EMAIL),
    Rule("SECRET", SECRET),
    Rule("IBAN", IBAN, iban_valid),
    Rule("CARD", CARD, luhn_valid),
    Rule("SSN", SSN),
    Rule("IP", IPV4),
    Rule("PHONE", PHONE, _plausible_phone),
    Rule("ADDRESS", STREET),
    Rule("NAME", NAME_INTRO, group=1),
    Rule("NAME", SIGN_OFF_NAME, group=1),
    Rule("NAME", SIGNATURE_LINE, group=1),
]


def known_name_rule(names: list[str]) -> Rule | None:
    cleaned = sorted({name.strip() for name in names if len(name.strip()) > 2}, key=len, reverse=True)
    if not cleaned:
        return None
    pattern = re.compile("|".join(re.escape(name) for name in cleaned), re.IGNORECASE)
    return Rule("NAME", pattern)


def find_spans(text: str, rules: list[Rule] | None = None) -> list[Span]:
    found: list[Span] = []
    for rule in rules or RULES:
        for match in rule.pattern.finditer(text):
            value = match.group(rule.group)
            if rule.validator and not rule.validator(value):
                continue
            found.append(Span(rule.label, match.start(rule.group), match.end(rule.group), value))
    return resolve_overlaps(found)


def resolve_overlaps(spans: list[Span]) -> list[Span]:
    ordered = sorted(spans, key=lambda span: (span.start, -(span.end - span.start)))
    kept: list[Span] = []
    for span in ordered:
        if kept and span.start < kept[-1].end:
            continue
        kept.append(span)
    return kept


def redact(text: str, known_names: list[str] | None = None) -> Redaction:
    rules = list(RULES)
    name_rule = known_name_rule(known_names or [])
    if name_rule:
        rules.append(name_rule)
    spans = find_spans(text, rules)
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
