"""Retrieval metrics over ranked lists of question ids."""

from collections.abc import Sequence


def rank_of(expected: int, ranked_ids: Sequence[int]) -> int | None:
    """1-based position of the expected id in the ranking, or None when it is missing."""
    try:
        return ranked_ids.index(expected) + 1
    except ValueError:
        return None


def hit_at_k(ranks: Sequence[int | None], k: int) -> float:
    """Share of queries whose expected id appears in the top k."""
    if not ranks:
        raise ValueError("no ranks to score")
    return sum(rank is not None and rank <= k for rank in ranks) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    """Mean of 1/rank over the queries, counting a miss as 0."""
    if not ranks:
        raise ValueError("no ranks to score")
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)
