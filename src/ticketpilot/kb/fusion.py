from __future__ import annotations

from collections import defaultdict
from typing import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]],
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[tuple[int, float]]:
    weights = weights or [1.0] * len(rankings)
    fused: dict[int, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking, start=1):
            fused[item] += weight / (k + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)
