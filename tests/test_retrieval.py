from patent_mvp.retrieval import merge_hybrid


def test_merge_hybrid_dedupes_and_scores() -> None:
    bm25 = [
        {"chunk_id": "c1", "publication_number": "p1", "text": "a", "section_type": "CLAIM", "score": 3.0},
        {"chunk_id": "c2", "publication_number": "p2", "text": "b", "section_type": "ABSTRACT", "score": 1.0},
    ]
    vec = [
        {"chunk_id": "c1", "publication_number": "p1", "text": "a", "section_type": "CLAIM", "score": 0.8},
        {"chunk_id": "c3", "publication_number": "p3", "text": "c", "section_type": "DESCRIPTION", "score": 0.9},
    ]

    merged = merge_hybrid(bm25, vec, topk=10)
    assert len(merged) == 3
    assert merged[0]["chunk_id"] == "c1"
    assert merged[0]["hybrid_score"] >= merged[1]["hybrid_score"]
