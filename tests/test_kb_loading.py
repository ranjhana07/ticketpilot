from pathlib import Path

import pytest

from ticketpilot.config import get_settings
from ticketpilot.kb.chunking import chunk_article, chunk_articles
from ticketpilot.kb.loader import load_articles, parse_front_matter


def test_front_matter_is_parsed():
    meta, body = parse_front_matter("---\nid: a\ntitle: Hello there\ncategory: x\n---\n\n# Hello\ntext")
    assert meta == {"id": "a", "title": "Hello there", "category": "x"}
    assert body.startswith("# Hello")


def test_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_articles(tmp_path)


def test_shipped_knowledge_base_is_well_formed():
    articles = load_articles(get_settings().kb_dir)
    assert len(articles) >= 30
    ids = [a.id for a in articles]
    assert len(ids) == len(set(ids))
    for article in articles:
        assert article.id == Path(article.path).stem
        assert article.title and article.category


def test_chunks_follow_headings_and_keep_ids():
    articles = load_articles(get_settings().kb_dir)
    article = next(a for a in articles if a.id == "reset-password")
    chunks = chunk_article(article)
    assert len(chunks) >= 2
    assert all(c.article_id == "reset-password" for c in chunks)
    assert {c.heading for c in chunks} >= {"Steps"}
    assert "](" not in " ".join(c.text for c in chunks)


def test_long_sections_are_split():
    articles = load_articles(get_settings().kb_dir)
    small = chunk_articles(articles, max_words=40)
    large = chunk_articles(articles, max_words=400)
    assert len(small) > len(large)
