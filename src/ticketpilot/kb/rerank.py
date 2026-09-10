from __future__ import annotations

from typing import Protocol, Sequence

from ticketpilot.kb.bm25 import tokenize

DEFAULT_RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER, batch_size: int = 16) -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = CrossEncoder(model_name, device="cpu")

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        pairs = [(query, passage) for passage in passages]
        return [float(value) for value in self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)]


class OverlapReranker:
    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        wanted = set(tokenize(query))
        if not wanted:
            return [0.0] * len(passages)
        scores = []
        for passage in passages:
            present = set(tokenize(passage))
            scores.append(len(wanted & present) / len(wanted))
        return scores
