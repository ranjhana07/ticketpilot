from __future__ import annotations

import re
from dataclasses import dataclass

STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "the be to of and a in that have i it for not on with he as you do at this but his by from "
        "they we say her she or an will my one all would there their what so up out if about who get "
        "which go me when make can like time no just him know take is are was can't please my our".split()
    ),
    "es": frozenset(
        "el la los las de que y en un una es se no te lo le da su por son con para al del me mi más "
        "pero sus como ya o este si porque esta entre cuando muy sin sobre también hay puedo quiero "
        "mi cuenta pedido cuál".split()
    ),
    "fr": frozenset(
        "le la les de des du un une et est en que qui dans pour pas sur au avec ce il elle je nous "
        "vous ils sont mon ma mes votre être avoir fait plus par mais ou où comme très bien quand "
        "pourriez voudrais compte commande".split()
    ),
    "de": frozenset(
        "der die das und ist nicht ich sie es ein eine zu den dem mit auf für von im ihr wir aber "
        "auch als wie bei oder nach noch nur wenn kann mein mir bitte wurde sind haben konto "
        "bestellung".split()
    ),
}

ACCENT_HINTS: dict[str, str] = {"es": "¿¡ñ", "fr": "çœèêàùû", "de": "äöüß"}
TOKEN = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)


@dataclass(frozen=True)
class Detection:
    language: str
    confidence: float


def detect_language(text: str, default: str = "en") -> Detection:
    tokens = [token.lower() for token in TOKEN.findall(text)]
    if not tokens:
        return Detection(default, 0.0)
    scores: dict[str, float] = {}
    for language, words in STOPWORDS.items():
        hits = sum(1 for token in tokens if token in words)
        accents = sum(text.lower().count(char) for char in ACCENT_HINTS.get(language, ""))
        scores[language] = hits + 0.5 * accents
    total = sum(scores.values())
    if total == 0:
        return Detection(default, 0.0)
    best = max(scores, key=lambda name: scores[name])
    return Detection(best, round(scores[best] / total, 3))
