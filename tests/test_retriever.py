import pytest

from ticketpilot.config import get_settings
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.kb.rerank import OverlapReranker
from ticketpilot.kb.retriever import MODES, HybridRetriever


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever.from_directory(get_settings().kb_dir, HashingEmbedder(), OverlapReranker())


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_finds_the_password_article(retriever, mode):
    hits = retriever.search("I forgot my password and the reset link expired", k=3, mode=mode)
    assert "reset-password" in [hit.article_id for hit in hits]


def test_hits_are_unique_per_article(retriever):
    hits = retriever.search("refund for add-on order", k=5)
    ids = [hit.article_id for hit in hits]
    assert len(ids) == len(set(ids))


def test_unknown_mode_is_rejected(retriever):
    with pytest.raises(ValueError):
        retriever.search("anything", mode="magic")


def test_rerank_without_reranker_falls_back_to_fusion():
    plain = HybridRetriever.from_directory(get_settings().kb_dir, HashingEmbedder())
    hits = plain.search("cancel my subscription", mode="hybrid_rerank")
    assert hits and hits[0].article_id == "cancel-subscription"


def test_hit_dict_has_citation_fields(retriever):
    payload = retriever.search("export workspace data", k=1)[0].to_dict()
    assert {"article_id", "title", "heading", "text", "score"} <= set(payload)
