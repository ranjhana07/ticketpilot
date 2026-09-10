from ticketpilot.evaluation.retrieval_eval import load_queries, score_ranking


def test_score_ranking_uses_first_relevant_position():
    scores = score_ranking(["a", "b", "c"], {"b", "c"})
    assert scores["mrr"] == 0.5
    assert scores["hit@1"] == 0.0 and scores["hit@3"] == 1.0


def test_no_relevant_hit_scores_zero():
    scores = score_ranking(["a"], {"z"})
    assert scores == {"mrr": 0.0, "hit@1": 0.0, "hit@3": 0.0, "hit@5": 0.0}


def test_query_set_points_at_existing_articles():
    from ticketpilot.config import get_settings
    from ticketpilot.kb.loader import load_articles

    ids = {article.id for article in load_articles(get_settings().kb_dir)}
    queries = load_queries()
    assert len(queries) >= 60
    for item in queries:
        assert item["relevant"] and set(item["relevant"]) <= ids
