from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from ticketpilot.config import get_settings
from ticketpilot.embeddings import get_embedder
from ticketpilot.kb.rerank import CrossEncoderReranker, OverlapReranker
from ticketpilot.kb.retriever import MODES, HybridRetriever

CUTOFFS = (1, 3, 5)
SEARCH_DEPTH = 10


def load_queries(path: Path | None = None) -> list[dict[str, object]]:
    source = path or get_settings().root / "eval" / "kb_queries.json"
    return json.loads(source.read_text(encoding="utf-8"))


def score_ranking(ranked_ids: list[str], relevant: set[str]) -> dict[str, float]:
    reciprocal_rank = 0.0
    for position, article_id in enumerate(ranked_ids, start=1):
        if article_id in relevant:
            reciprocal_rank = 1.0 / position
            break
    result = {"mrr": reciprocal_rank}
    for cutoff in CUTOFFS:
        result[f"hit@{cutoff}"] = float(any(article_id in relevant for article_id in ranked_ids[:cutoff]))
    return result


def evaluate_mode(retriever: HybridRetriever, queries: list[dict[str, object]], mode: str) -> dict[str, float]:
    totals = {"mrr": 0.0, **{f"hit@{cutoff}": 0.0 for cutoff in CUTOFFS}}
    started = time.perf_counter()
    for item in queries:
        hits = retriever.search(str(item["query"]), k=SEARCH_DEPTH, mode=mode)
        scores = score_ranking([hit.article_id for hit in hits], set(item["relevant"]))
        for key, value in scores.items():
            totals[key] += value
    elapsed = time.perf_counter() - started
    row = {key: round(value / len(queries), 4) for key, value in totals.items()}
    row["ms_per_query"] = round(1000 * elapsed / len(queries), 2)
    return row


def run(output_dir: Path, embedder_name: str = "minilm", reranker_name: str = "cross-encoder") -> list[dict[str, object]]:
    queries = load_queries()
    reranker = CrossEncoderReranker() if reranker_name == "cross-encoder" else OverlapReranker()
    retriever = HybridRetriever.from_directory(get_settings().kb_dir, get_embedder(embedder_name), reranker)
    rows = []
    for mode in MODES:
        evaluate_mode(retriever, queries[:3], mode)
        metrics = evaluate_mode(retriever, queries, mode)
        rows.append(
            {
                "mode": mode,
                "embedder": embedder_name,
                "reranker": reranker_name if mode == "hybrid_rerank" else "",
                "n_queries": len(queries),
                "n_chunks": len(retriever.chunks),
                **metrics,
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "retrieval.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (output_dir / "retrieval.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows
