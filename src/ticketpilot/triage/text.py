from __future__ import annotations

import re

QUOTED_LINE = re.compile(r"^\s*>.*$", re.MULTILINE)
REPLY_HEADER = re.compile(r"^On .{5,80} wrote:\s*$.*", re.MULTILINE | re.DOTALL)
WHITESPACE = re.compile(r"[ \t]+")
BLANK_RUNS = re.compile(r"\n{3,}")


def strip_quoted_reply(text: str) -> str:
    text = REPLY_HEADER.sub("", text)
    return QUOTED_LINE.sub("", text)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = WHITESPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return BLANK_RUNS.sub("\n\n", text).strip()


def clean_ticket_text(text: str) -> str:
    return normalize_whitespace(strip_quoted_reply(text))
