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
            root = word[: -len(suffix)]
            if root[-1] == root[-2] and root[-1] not in "aeiouls":
                root = root[:-1]
            return root
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
        self.postings: dict[str, list[int]] = {}
        for position, counts in enumerate(self.term_counts):
            for term in counts:
                self.postings.setdefault(term, []).append(position)
        size = len(documents)
        self.idf = {
            term: math.log(1 + (size - df + 0.5) / (df + 0.5)) for term, df in document_frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        result = [0.0] * len(self.term_counts)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for position in self.postings[term]:
                frequency = self.term_counts[position][term]
                norm = frequency + self.k1 * (1 - self.b + self.b * self.lengths[position] / self.average_length)
                result[position] += idf * frequency * (self.k1 + 1) / norm
        return result

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scored = [(index, score) for index, score in enumerate(self.scores(query)) if score > 0]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
