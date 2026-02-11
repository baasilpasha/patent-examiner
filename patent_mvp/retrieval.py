from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patent_mvp.db import PostgresStore
    from patent_mvp.embeddings import EmbeddingProvider
    from patent_mvp.search_index import OpenSearchStore


@dataclass
class RetrievalResult:
    chunks: list[dict]
    patents: list[dict]


def merge_hybrid(
    bm25_hits: list[dict],
    vector_hits: list[dict],
    topk: int,
    bm25_weight: float = 0.45,
    vector_weight: float = 0.55,
) -> list[dict]:
    merged: dict[str, dict] = {}
    bm25_max = max((h["score"] for h in bm25_hits), default=1.0)
    vec_max = max((h["score"] for h in vector_hits), default=1.0)

    for hit in bm25_hits:
        data = merged.setdefault(hit["chunk_id"], {**hit, "bm25_score": 0.0, "vec_score": 0.0})
        data["bm25_score"] = hit["score"] / bm25_max if bm25_max else 0.0

    for hit in vector_hits:
        data = merged.setdefault(hit["chunk_id"], {**hit, "bm25_score": 0.0, "vec_score": 0.0})
        data["vec_score"] = hit["score"] / vec_max if vec_max else 0.0

    for hit in merged.values():
        hit["hybrid_score"] = bm25_weight * hit["bm25_score"] + vector_weight * hit["vec_score"]

    return sorted(merged.values(), key=lambda x: x["hybrid_score"], reverse=True)[:topk]


def aggregate_patents(chunk_hits: list[dict]) -> list[dict]:
    acc: dict[str, list[float]] = defaultdict(list)
    for chunk in chunk_hits:
        acc[chunk["publication_number"]].append(chunk["hybrid_score"])
    patents = [{"publication_number": pub, "score": max(scores), "supporting_chunks": len(scores)} for pub, scores in acc.items()]
    patents.sort(key=lambda x: x["score"], reverse=True)
    return patents


def run_search(
    query: str,
    topk: int,
    topk_bm25: int,
    topk_vec: int,
    graph_expand: bool,
    db: "PostgresStore",
    index: "OpenSearchStore",
    embedder: "EmbeddingProvider",
) -> RetrievalResult:
    bm25_hits = index.bm25_search(query, topk=topk_bm25)
    query_vec = embedder.embed([query])[0]
    vec_hits = db.vector_search(query_vec, topk=topk_vec)
    merged = merge_hybrid(bm25_hits, vec_hits, topk=max(topk, 200))

    if graph_expand:
        seeds = {h["publication_number"] for h in merged[:50]}
        neighbors = db.graph_neighbors(seeds)
        for hit in merged:
            if hit["publication_number"] in neighbors:
                hit["hybrid_score"] *= 1.05
        merged = sorted(merged, key=lambda x: x["hybrid_score"], reverse=True)

    merged = merged[:topk]
    patents = aggregate_patents(merged)
    return RetrievalResult(chunks=merged, patents=patents)
