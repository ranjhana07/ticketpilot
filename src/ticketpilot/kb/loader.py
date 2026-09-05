from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    category: str
    body: str
    path: Path


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    _, header, body = raw.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def load_articles(directory: Path) -> list[Article]:
    articles = []
    for path in sorted(directory.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        articles.append(
            Article(
                id=meta.get("id", path.stem),
                title=meta.get("title", path.stem.replace("-", " ").title()),
                category=meta.get("category", "general"),
                body=body,
                path=path,
            )
        )
    if not articles:
        raise FileNotFoundError(f"no markdown articles found in {directory}")
    return articles
