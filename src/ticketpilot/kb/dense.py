from __future__ import annotations

from typing import Sequence

import numpy as np

from ticketpilot.embeddings import Embedder


class DenseIndex:
    def __init__(self, embedder: Embedder, documents: Sequence[str]) -> None:
        self.embedder = embedder
        self.vectors = embedder.encode(list(documents))

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scores = self.vectors @ self.embedder.encode([query])[0]
        order = np.argsort(-scores)[:k]
        return [(int(index), float(scores[index])) for index in order]
