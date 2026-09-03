from __future__ import annotations

import hashlib
import re
from typing import Protocol, Sequence

import numpy as np

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class HashingEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little")
        return value % self.dim, 1.0 if (value >> 40) & 1 else -1.0

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = TOKEN.findall(text.lower())
            features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
            for feature in features:
                column, sign = self._bucket(feature)
                matrix[row, column] += sign
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, batch_size: int = 64) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self.model.encode(
            list(texts), batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vectors, dtype=np.float32)


def get_embedder(name: str = "minilm") -> Embedder:
    if name == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder()
