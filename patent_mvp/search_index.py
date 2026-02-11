from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from opensearchpy import OpenSearch

from patent_mvp.models import EvidenceChunk


class OpenSearchStore:
    def __init__(self, url: str, index_name: str) -> None:
        self.client = OpenSearch(hosts=[url], use_ssl=False, verify_certs=False)
        self.index_name = index_name

    def ensure_index(self, mapping_path: Path) -> None:
        if self.client.indices.exists(index=self.index_name):
            return
        with mapping_path.open() as fh:
            body = json.load(fh)
        self.client.indices.create(index=self.index_name, body=body)

    def upsert_chunks(self, chunks: Iterable[EvidenceChunk]) -> None:
        for chunk in chunks:
            body = {
                "chunk_id": chunk.chunk_id,
                "publication_number": chunk.publication_number,
                "section_type": chunk.section_type,
                "text": chunk.text,
                "metadata": chunk.metadata,
            }
            self.client.index(index=self.index_name, id=chunk.chunk_id, body=body, refresh=False)
        self.client.indices.refresh(index=self.index_name)

    def bm25_search(self, query: str, topk: int) -> list[dict]:
        response = self.client.search(
            index=self.index_name,
            body={
                "size": topk,
                "query": {"match": {"text": {"query": query}}},
                "highlight": {"fields": {"text": {"fragment_size": 160, "number_of_fragments": 2}}},
            },
        )
        hits = []
        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            hits.append(
                {
                    "chunk_id": src["chunk_id"],
                    "publication_number": src["publication_number"],
                    "text": src["text"],
                    "section_type": src["section_type"],
                    "score": float(hit.get("_score", 0.0)),
                    "highlights": hit.get("highlight", {}).get("text", []),
                }
            )
        return hits
