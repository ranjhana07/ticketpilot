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
