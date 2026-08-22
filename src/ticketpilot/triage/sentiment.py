from __future__ import annotations

import re
from dataclasses import dataclass

NEGATIVE = {
    "angry": 2.0, "furious": 3.0, "terrible": 2.5, "awful": 2.5, "worst": 2.5, "useless": 2.0,
    "frustrating": 2.0, "frustrated": 2.0, "unacceptable": 2.5, "ridiculous": 2.0, "broken": 1.5,
    "crashes": 1.5, "crash": 1.5, "fails": 1.5, "failed": 1.5, "wrong": 1.0, "error": 1.0,
    "never": 0.8, "again": 0.6, "still": 0.6, "disappointed": 2.0, "annoying": 1.5, "scam": 3.0,
    "stolen": 2.5, "phishing": 1.5, "locked": 1.2, "missing": 1.0, "charged": 0.8, "twice": 1.0,
    "complaint": 1.5, "cancel": 0.8, "refund": 0.6,
}
POSITIVE = {
    "thanks": 1.0, "thank": 1.0, "great": 1.5, "love": 2.0, "awesome": 2.0, "helpful": 1.5,
    "appreciate": 1.5, "happy": 1.5, "good": 1.0, "perfect": 2.0, "excellent": 2.0, "nice": 1.0,
}
URGENCY_TERMS = {
    "urgent": 1.0, "asap": 1.0, "emergency": 1.0, "immediately": 0.8, "now": 0.4, "today": 0.5,
    "blocked": 0.7, "blocking": 0.7, "production": 0.7, "outage": 0.9, "down": 0.5, "deadline": 0.6,
    "hour": 0.4, "locked": 0.5, "hacked": 0.9, "compromised": 0.9, "unauthorized": 0.7,
}
CALM_TERMS = {"whenever": 0.5, "rush": 0.4, "curious": 0.3, "chance": 0.3, "eventually": 0.3}
NEGATORS = {"not", "no", "never", "don't", "doesn't", "isn't", "wasn't", "can't", "cannot", "without"}
TOKEN = re.compile(r"[A-Za-z']+")


@dataclass(frozen=True)
class SentimentResult:
    score: float
    label: str
    urgency: float


def _squash(value: float, scale: float) -> float:
    return max(-1.0, min(1.0, value / (abs(value) + scale)))


def score_text(text: str) -> SentimentResult:
    words = TOKEN.findall(text)
    lowered = [word.lower() for word in words]
    raw = 0.0
    for position, word in enumerate(lowered):
        weight = POSITIVE.get(word, 0.0) - NEGATIVE.get(word, 0.0)
        if weight == 0.0:
            continue
        window = lowered[max(0, position - 3):position]
        if any(token in NEGATORS for token in window) and word in POSITIVE:
            weight = -abs(weight) * 0.8
        raw += weight
    shouting = sum(1 for word in words if len(word) > 3 and word.isupper())
    exclamations = text.count("!")
    raw -= 0.4 * shouting + 0.2 * min(exclamations, 5)
    score = round(_squash(raw, 4.0), 3)
    urgency_raw = sum(URGENCY_TERMS.get(word, 0.0) for word in lowered)
    urgency_raw -= sum(CALM_TERMS.get(word, 0.0) for word in lowered)
    urgency_raw += 0.3 * shouting + 0.15 * min(exclamations, 4)
    urgency = round(max(0.0, min(1.0, urgency_raw / (urgency_raw + 1.5))) if urgency_raw > 0 else 0.0, 3)
    label = "negative" if score <= -0.25 else "positive" if score >= 0.25 else "neutral"
    return SentimentResult(score, label, urgency)
