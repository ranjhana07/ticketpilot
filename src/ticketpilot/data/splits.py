from __future__ import annotations

from collections import Counter
from typing import Callable, Sequence, TypeVar

from sklearn.model_selection import train_test_split

T = TypeVar("T")


def stratified_split(
    items: Sequence[T],
    key: Callable[[T], str],
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[list[T], list[T]]:
    labels = [key(item) for item in items]
    train, test = train_test_split(list(items), test_size=test_size, random_state=seed, stratify=labels)
    return train, test


def subsample_per_class(items: Sequence[T], key: Callable[[T], str], per_class: int, seed: int = 42) -> list[T]:
    import random

    rng = random.Random(seed)
    shuffled = list(items)
    rng.shuffle(shuffled)
    taken: Counter[str] = Counter()
    chosen = []
    for item in shuffled:
        label = key(item)
        if taken[label] < per_class:
            taken[label] += 1
            chosen.append(item)
    return chosen
