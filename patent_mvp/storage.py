from __future__ import annotations

import json
from typing import Iterable

import psycopg
from opensearchpy import OpenSearch

from patent_mvp.models import EvidenceChunk, PatentRecord


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def conn(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)

    def upsert_patent(self, patent: PatentRecord) -> None:
        with self.conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patents(publication_number, grant_date, title, abstract, raw_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (publication_number) DO UPDATE
                  SET grant_date=EXCLUDED.grant_date, title=EXCLUDED.title, abstract=EXCLUDED.abstract, raw_json=EXCLUDED.raw_json
                """,
                (patent.publication_number, patent.grant_date, patent.title, patent.abstract, json.dumps(patent.raw_json)),
            )
            for cpc in patent.cpc_codes:
                cur.execute(
                    "INSERT INTO patent_cpc(publication_number, cpc_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (patent.publication_number, cpc),
                )
            for cited in patent.citations:
                cur.execute(
                    "INSERT INTO patent_citations(publication_number, cited_publication_number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (patent.publication_number, cited),
                )

    def upsert_chunks(self, chunks: Iterable[EvidenceChunk]) -> None:
        with self.conn() as conn, conn.cursor() as cur:
            for c in chunks:
                cur.execute(
                    """
                    INSERT INTO evidence_chunks(chunk_id, publication_number, section_type, claim_num, para_id, is_independent, text, text_hash, metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (chunk_id) DO UPDATE
                    SET text=EXCLUDED.text, metadata=EXCLUDED.metadata
                    """,
                    (
                        c.chunk_id,
                        c.publication_number,
                        c.section_type,
                        c.claim_num,
                        c.para_id,
                        c.is_independent,
                        c.text,
                        c.metadata.get("text_hash", ""),
                        json.dumps(c.metadata),
                    ),
                )

    def update_embedding(self, chunk_id: str, embedding: list[float]) -> None:
        with self.conn() as conn, conn.cursor() as cur:
            vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            cur.execute("UPDATE evidence_chunks SET embedding=%s::vector WHERE chunk_id=%s", (vector_literal, chunk_id))

    def vector_search(self, query_embedding: list[float], topk: int) -> list[tuple[str, str, float]]:
        with self.conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, publication_number, 1 - (embedding <=> %s::vector) AS score
                FROM evidence_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                ("[" + ",".join(str(x) for x in query_embedding) + "]", "[" + ",".join(str(x) for x in query_embedding) + "]", topk),
            )
            return [(r[0], r[1], float(r[2])) for r in cur.fetchall()]

    def graph_expand_patents(self, patents: set[str], limit: int = 300) -> set[str]:
        if not patents:
            return set()
        with self.conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT pc2.publication_number
                FROM patent_cpc pc1
                JOIN patent_cpc pc2 ON pc1.cpc_code = pc2.cpc_code
                WHERE pc1.publication_number = ANY(%s)
                LIMIT %s
                """,
                (list(patents), limit),
            )
            cpc_neighbors = {r[0] for r in cur.fetchall()}
            cur.execute(
                """
                SELECT DISTINCT cited_publication_number
                FROM patent_citations
                WHERE publication_number = ANY(%s)
                LIMIT %s
                """,
                (list(patents), limit),
            )
            cited = {r[0] for r in cur.fetchall()}
        return patents | cpc_neighbors | cited


class OpenSearchStore:
    def __init__(self, base_url: str, index_name: str) -> None:
        self.client = OpenSearch(hosts=[base_url])
        self.index_name = index_name

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            return
        mapping = {
            "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "publication_number": {"type": "keyword"},
                    "section_type": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            },
        }
        self.client.indices.create(index=self.index_name, body=mapping)

    def index_chunks(self, chunks: Iterable[EvidenceChunk]) -> None:
        for c in chunks:
            self.client.index(
                index=self.index_name,
                id=c.chunk_id,
                body={
                    "chunk_id": c.chunk_id,
                    "publication_number": c.publication_number,
                    "section_type": c.section_type,
                    "text": c.text,
                },
                refresh=False,
            )
        self.client.indices.refresh(index=self.index_name)

    def bm25_search(self, query: str, topk: int) -> list[tuple[str, str, float, str]]:
        response = self.client.search(
            index=self.index_name,
            body={
                "size": topk,
                "query": {"match": {"text": query}},
                "highlight": {"fields": {"text": {}}},
            },
        )
        out: list[tuple[str, str, float, str]] = []
        for h in response["hits"]["hits"]:
            src = h["_source"]
            snippet = " ".join(h.get("highlight", {}).get("text", [])[:1])
            out.append((src["chunk_id"], src["publication_number"], float(h["_score"]), snippet))
        return out
