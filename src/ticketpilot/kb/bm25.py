from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

STOPWORDS = frozenset(
    "a an and are as at be but by for from has have i if in into is it its my of on or our so that the "
    "their then there these they this to was we what when where which who will with you your can do does "
    "how not no me please".split()
)
TOKEN = re.compile(r"[a-z0-9]+")


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    return [stem(token) for token in TOKEN.findall(text.lower()) if token not in STOPWORDS]


class BM25Index:
    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.term_counts = [Counter(tokenize(document)) for document in documents]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_length = sum(self.lengths) / max(1, len(self.lengths))
        document_frequency: Counter[str] = Counter()
        for counts in self.term_counts:
            document_frequency.update(counts.keys())
        size = len(documents)
        self.idf = {
            term: math.log(1 + (size - df + 0.5) / (df + 0.5)) for term, df in document_frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        result = []
        for counts, length in zip(self.term_counts, self.lengths):
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                norm = frequency + self.k1 * (1 - self.b + self.b * length / self.average_length)
                score += self.idf[term] * frequency * (self.k1 + 1) / norm
            result.append(score)
        return result

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scored = [(index, score) for index, score in enumerate(self.scores(query)) if score > 0]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
