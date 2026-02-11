from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from patent_mvp.embeddings import EmbeddingProvider

if TYPE_CHECKING:
    from patent_mvp.storage import OpenSearchStore, PostgresStore


def merge_scores(
    bm25: list[tuple[str, str, float, str]],
    vec: list[tuple[str, str, float]],
    w_bm25: float = 0.5,
    w_vec: float = 0.5,
) -> list[dict]:
    merged: dict[str, dict] = {}
    max_bm25 = max((x[2] for x in bm25), default=1.0)
    max_vec = max((x[2] for x in vec), default=1.0)

    for chunk_id, pub, score, snippet in bm25:
        merged.setdefault(chunk_id, {"chunk_id": chunk_id, "publication_number": pub, "score": 0.0, "snippet": snippet})
        merged[chunk_id]["score"] += w_bm25 * (score / max_bm25)

    for chunk_id, pub, score in vec:
        merged.setdefault(chunk_id, {"chunk_id": chunk_id, "publication_number": pub, "score": 0.0, "snippet": ""})
        merged[chunk_id]["score"] += w_vec * (score / max_vec)

    return sorted(merged.values(), key=lambda x: x["score"], reverse=True)


def rank_patents(chunks: list[dict]) -> list[dict]:
    patent_scores: dict[str, float] = defaultdict(float)
    for c in chunks:
        patent_scores[c["publication_number"]] += float(c["score"])
    return [{"publication_number": p, "score": s} for p, s in sorted(patent_scores.items(), key=lambda kv: kv[1], reverse=True)]


def hybrid_search(
    query: str,
    embedder: EmbeddingProvider,
    pg: "PostgresStore",
    os_store: "OpenSearchStore",
    topk: int = 50,
    topk_bm25: int = 200,
    topk_vec: int = 200,
    graph_expand: bool = False,
) -> dict:
    bm25 = os_store.bm25_search(query, topk_bm25)
    q_vec = embedder.embed([query])[0]
    vec = pg.vector_search(q_vec, topk_vec)
    merged = merge_scores(bm25, vec)

    if graph_expand:
        seeds = {x["publication_number"] for x in merged[:topk]}
        expanded = pg.graph_expand_patents(seeds)
        for item in merged:
            if item["publication_number"] in expanded:
                item["score"] *= 1.05
        merged = sorted(merged, key=lambda x: x["score"], reverse=True)

    top_chunks = merged[:topk]
    patents = rank_patents(top_chunks)
    return {"chunks": top_chunks, "patents": patents}
