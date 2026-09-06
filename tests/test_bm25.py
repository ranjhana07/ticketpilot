from ticketpilot.kb.bm25 import BM25Index, stem, tokenize

DOCS = [
    "Reset your password with the emailed link, links expire after 60 minutes",
    "Download invoices as PDF from the billing page",
    "Cancel the subscription before renewal to stop charges",
]


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("The links are expiring") == ["link", "expir"]
    assert stem("cat") == "cat"


def test_exact_term_match_ranks_first():
    index = BM25Index(DOCS)
    assert index.search("password reset link")[0][0] == 0
    assert index.search("invoices pdf")[0][0] == 1


def test_stemming_matches_inflections():
    index = BM25Index(DOCS)
    assert index.search("cancelling subscriptions")[0][0] == 2


def test_query_without_known_terms_returns_nothing():
    assert BM25Index(DOCS).search("zzzz qqqq") == []


def test_rarer_terms_weigh_more():
    index = BM25Index(["billing page page page", "billing refund"])
    assert index.search("refund")[0][0] == 1
