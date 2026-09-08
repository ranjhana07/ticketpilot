from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ticketpilot.embeddings import Embedder
from ticketpilot.kb.bm25 import BM25Index
from ticketpilot.kb.chunking import Chunk, chunk_articles
from ticketpilot.kb.dense import DenseIndex
from ticketpilot.kb.fusion import reciprocal_rank_fusion
from ticketpilot.kb.loader import load_articles
from ticketpilot.kb.rerank import Reranker

MODES = ("bm25", "dense", "hybrid", "hybrid_rerank")


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float

    @property
    def article_id(self) -> str:
        return self.chunk.article_id

    def to_dict(self) -> dict[str, object]:
        return {
            "article_id": self.chunk.article_id,
            "title": self.chunk.title,
            "heading": self.chunk.heading,
            "text": self.chunk.text,
            "score": round(self.score, 4),
        }


class HybridRetriever:
    def __init__(self, chunks: list[Chunk], embedder: Embedder, reranker: Reranker | None = None) -> None:
        self.chunks = chunks
        self.reranker = reranker
        documents = [chunk.searchable for chunk in chunks]
        self.bm25 = BM25Index(documents)
        self.dense = DenseIndex(embedder, documents)

    @classmethod
    def from_directory(cls, directory: Path, embedder: Embedder, reranker: Reranker | None = None) -> "HybridRetriever":
        return cls(chunk_articles(load_articles(directory)), embedder, reranker)

    def _ranked(self, query: str, mode: str, pool: int) -> list[tuple[int, float]]:
        if mode == "bm25":
            return self.bm25.search(query, pool)
        if mode == "dense":
            return self.dense.search(query, pool)
        lexical = [index for index, _ in self.bm25.search(query, pool)]
        semantic = [index for index, _ in self.dense.search(query, pool)]
        return reciprocal_rank_fusion([lexical, semantic])[:pool]

    def search(self, query: str, k: int = 5, mode: str = "hybrid_rerank", pool: int = 20) -> list[Hit]:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}, expected one of {MODES}")
        ranked = self._ranked(query, "hybrid" if mode == "hybrid_rerank" else mode, pool)
        if mode == "hybrid_rerank" and self.reranker is not None and ranked:
            texts = [self.chunks[index].searchable for index, _ in ranked]
            scores = self.reranker.score(query, texts)
            ranked = sorted(zip((index for index, _ in ranked), scores), key=lambda pair: pair[1], reverse=True)
        seen: set[str] = set()
        hits: list[Hit] = []
        for index, score in ranked:
            chunk = self.chunks[index]
            if chunk.article_id in seen:
                continue
            seen.add(chunk.article_id)
            hits.append(Hit(chunk, float(score)))
            if len(hits) == k:
                break
        return hits
