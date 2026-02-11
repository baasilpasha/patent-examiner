from patent_mvp.search import merge_scores


def test_hybrid_merge_and_dedupe() -> None:
    bm25 = [
        ("c1", "US1", 10.0, "snippet"),
        ("c2", "US2", 5.0, "snippet"),
    ]
    vec = [
        ("c1", "US1", 0.9),
        ("c3", "US3", 0.8),
    ]
    out = merge_scores(bm25, vec)
    ids = [x["chunk_id"] for x in out]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert ids[0] == "c1"
