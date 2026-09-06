from __future__ import annotations

import re
from dataclasses import dataclass

from ticketpilot.kb.loader import Article

HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    article_id: str
    title: str
    heading: str
    text: str

    @property
    def searchable(self) -> str:
        return f"{self.title}. {self.heading}. {self.text}"


def _sections(body: str) -> list[tuple[str, str]]:
    matches = list(HEADING.finditer(body))
    if not matches:
        return [("", body.strip())]
    sections = []
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(body)
        text = body[match.end():end].strip()
        if text:
            sections.append((match.group(2).strip(), text))
    return sections


def chunk_article(article: Article, max_words: int = 140) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, text in _sections(article.body):
        text = LINK.sub(r"\1", text)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        current: list[str] = []
        words = 0
        for paragraph in paragraphs:
            size = len(paragraph.split())
            if current and words + size > max_words:
                chunks.append(Chunk(f"{article.id}#{len(chunks)}", article.id, article.title, heading, "\n".join(current)))
                current, words = [], 0
            current.append(paragraph)
            words += size
        if current:
            chunks.append(Chunk(f"{article.id}#{len(chunks)}", article.id, article.title, heading, "\n".join(current)))
    return chunks


def chunk_articles(articles: list[Article], max_words: int = 140) -> list[Chunk]:
    return [chunk for article in articles for chunk in chunk_article(article, max_words)]
