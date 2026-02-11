from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from typing import Iterable

import psycopg
from pgvector.psycopg import register_vector

from patent_mvp.models import EvidenceChunk, PatentDocument


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connection(self):
        with psycopg.connect(self.dsn) as conn:
            register_vector(conn)
            yield conn

    def get_last_week(self, source: str) -> str | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT last_week FROM ingestion_state WHERE source = %s", (source,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_last_week(self, source: str, week: str) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_state(source, last_week)
                VALUES (%s, %s)
                ON CONFLICT (source)
                DO UPDATE SET last_week = EXCLUDED.last_week, updated_at = NOW()
                """,
                (source, week),
            )
            conn.commit()

    def upsert_patent(self, patent: PatentDocument) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patents(publication_number, grant_date, title, abstract_text, summary_text, description_text, raw_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (publication_number)
                DO UPDATE SET grant_date = EXCLUDED.grant_date,
                              title = EXCLUDED.title,
                              abstract_text = EXCLUDED.abstract_text,
                              summary_text = EXCLUDED.summary_text,
                              description_text = EXCLUDED.description_text,
                              raw_json = EXCLUDED.raw_json
                """,
                (
                    patent.publication_number,
                    patent.grant_date or None,
                    patent.title,
                    patent.abstract,
                    "\n".join(patent.summary_paragraphs),
                    "\n".join(patent.description_paragraphs),
                    json.dumps(patent.raw),
                ),
            )
            cur.execute("DELETE FROM patent_citations WHERE citing_publication = %s", (patent.publication_number,))
            cur.execute("DELETE FROM patent_cpc WHERE publication_number = %s", (patent.publication_number,))
            for cited in patent.citations:
                cur.execute(
                    "INSERT INTO patent_citations(citing_publication, cited_publication) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (patent.publication_number, cited),
                )
            for cpc in patent.cpc_codes:
                cur.execute(
                    "INSERT INTO patent_cpc(publication_number, cpc_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (patent.publication_number, cpc),
                )
            conn.commit()

    def upsert_chunks(self, chunks: Iterable[EvidenceChunk]) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO chunks(chunk_id, publication_number, section_type, claim_num, para_id, is_dependent, text, text_hash, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (chunk_id)
                    DO UPDATE SET text = EXCLUDED.text,
                                  metadata = EXCLUDED.metadata,
                                  claim_num = EXCLUDED.claim_num,
                                  para_id = EXCLUDED.para_id,
                                  is_dependent = EXCLUDED.is_dependent
                    """,
                    (
                        chunk.chunk_id,
                        chunk.publication_number,
                        chunk.section_type,
                        chunk.claim_num,
                        chunk.para_id,
                        chunk.is_dependent,
                        chunk.text,
                        chunk.text_hash,
                        json.dumps(chunk.metadata),
                    ),
                )
            conn.commit()

    def fetch_chunks_missing_embeddings(self, limit: int = 1000) -> list[tuple[str, str]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT chunk_id, text FROM chunks WHERE embedding IS NULL LIMIT %s", (limit,))
            return [(row[0], row[1]) for row in cur.fetchall()]

    def update_embeddings(self, vectors: list[tuple[str, list[float]]]) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            for chunk_id, emb in vectors:
                cur.execute("UPDATE chunks SET embedding = %s WHERE chunk_id = %s", (emb, chunk_id))
            conn.commit()

    def vector_search(self, query_embedding: list[float], topk: int) -> list[dict]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, publication_number, text, section_type,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, topk),
            )
            rows = cur.fetchall()
        return [
            {"chunk_id": r[0], "publication_number": r[1], "text": r[2], "section_type": r[3], "score": float(r[4])}
            for r in rows
        ]

    def graph_neighbors(self, publications: set[str], limit: int = 200) -> set[str]:
        if not publications:
            return set()
        pubs = tuple(publications)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT cited_publication FROM patent_citations
                WHERE citing_publication = ANY(%s)
                LIMIT %s
                """,
                (list(pubs), limit),
            )
            cited = {r[0] for r in cur.fetchall()}
            cur.execute(
                """
                SELECT DISTINCT pc2.publication_number
                FROM patent_cpc pc1
                JOIN patent_cpc pc2 ON split_part(pc1.cpc_code, '/', 1) = split_part(pc2.cpc_code, '/', 1)
                WHERE pc1.publication_number = ANY(%s)
                LIMIT %s
                """,
                (list(pubs), limit),
            )
            cpc_neighbors = {r[0] for r in cur.fetchall()}
        return cited | cpc_neighbors
