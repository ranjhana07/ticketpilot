import numpy as np

from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.kb.dense import DenseIndex
from ticketpilot.kb.fusion import reciprocal_rank_fusion


def test_items_ranked_high_in_both_lists_win():
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 2, 9]])
    assert [item for item, _ in fused][:2] == [3, 2]


def test_weights_shift_the_outcome():
    plain = reciprocal_rank_fusion([[1, 2], [2, 1]])
    heavy = reciprocal_rank_fusion([[1, 2], [2, 1]], weights=[3.0, 1.0])
    assert heavy[0][0] == 1
    assert plain[0][1] == plain[1][1]


def test_item_missing_from_one_list_still_counts():
    fused = dict(reciprocal_rank_fusion([[1], [2]]))
    assert set(fused) == {1, 2}


def test_dense_index_orders_by_similarity():
    docs = ["reset password link", "download invoice pdf", "cancel subscription renewal"]
    index = DenseIndex(HashingEmbedder(), docs)
    hits = index.search("invoice pdf download", k=2)
    assert hits[0][0] == 1
    assert len(hits) == 2
    assert hits[0][1] >= hits[1][1]
    assert np.isfinite(hits[0][1])
