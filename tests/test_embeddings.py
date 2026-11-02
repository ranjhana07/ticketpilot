import numpy as np

from ticketpilot.embeddings import HashingEmbedder


def test_vectors_are_normalised_and_deterministic():
    embedder = HashingEmbedder()
    first = embedder.encode(["reset my password", "refund please"])
    second = embedder.encode(["reset my password", "refund please"])
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0)
    assert np.array_equal(first, second)


def test_similar_texts_score_higher():
    embedder = HashingEmbedder()
    a, b, c = embedder.encode(
        ["please reset my password", "reset password please", "invoice for last quarter"]
    )
    assert a @ b > a @ c


def test_empty_text_gives_zero_vector():
    assert not HashingEmbedder().encode([""]).any()


class CountingEmbedder:
    def __init__(self):
        self.seen = []
        self.inner = HashingEmbedder()

    def encode(self, texts):
        self.seen.extend(texts)
        return self.inner.encode(texts)


def test_cached_embedder_encodes_each_text_once():
    from ticketpilot.embeddings import CachedEmbedder

    counting = CountingEmbedder()
    cached = CachedEmbedder(counting)
    first = cached.encode(["a b", "c d", "a b"])
    second = cached.encode(["c d", "e f"])
    assert counting.seen == ["a b", "c d", "e f"]
    assert np.array_equal(first[0], first[2])
    assert second.shape[0] == 2


def test_cached_embedder_evicts_when_full():
    from ticketpilot.embeddings import CachedEmbedder

    cached = CachedEmbedder(HashingEmbedder(), max_entries=2)
    cached.encode(["one", "two"])
    cached.encode(["three"])
    assert len(cached._cache) == 1
