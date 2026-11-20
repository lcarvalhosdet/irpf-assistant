"""Retrieval metrics on hand-checked rankings."""

import pytest

from irpf_assistant.metrics import hit_at_k, mean_reciprocal_rank, rank_of


def test_rank_of_is_one_based_and_none_when_missing() -> None:
    assert rank_of(7, [7, 3, 9]) == 1
    assert rank_of(9, [7, 3, 9]) == 3
    assert rank_of(5, [7, 3, 9]) is None


def test_hit_at_k_counts_ranks_within_k() -> None:
    ranks = [1, 3, None, 6]
    assert hit_at_k(ranks, 1) == 0.25
    assert hit_at_k(ranks, 3) == 0.5
    assert hit_at_k(ranks, 10) == 0.75


def test_mean_reciprocal_rank_counts_misses_as_zero() -> None:
    assert mean_reciprocal_rank([1, 2, None, 4]) == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)


@pytest.mark.parametrize("metric", [lambda r: hit_at_k(r, 5), mean_reciprocal_rank])
def test_metrics_refuse_an_empty_run(metric) -> None:
    with pytest.raises(ValueError, match="no ranks"):
        metric([])
