from __future__ import annotations

import logging
from pathlib import Path

from patent_mvp.chunker import build_chunks, has_cpc_prefix, write_chunk_jsonl
from patent_mvp.config import SETTINGS
from patent_mvp.downloader import PTGRXMLDownloader
from patent_mvp.embeddings import SentenceTransformerProvider
from patent_mvp.parser import parse_week_zip
from patent_mvp.storage import OpenSearchStore, PostgresStore

LOGGER = logging.getLogger(__name__)


def run_ingest(weeks: int = 12, cpc_prefix: str = "G06F", since_last: bool = False) -> None:
    downloader = PTGRXMLDownloader(data_root=SETTINGS.data_root)
    selected = downloader.select_weeks(weeks=weeks, since_last=since_last)
    if not selected:
        LOGGER.info("No new weeks to process")
        return
    LOGGER.info("Resolved %s week(s) for ingest: %s", len(selected), selected)

    pg = PostgresStore(SETTINGS.postgres_dsn)
    os_store = OpenSearchStore(SETTINGS.opensearch_url, SETTINGS.opensearch_index)
    os_store.ensure_index()
    embedder = SentenceTransformerProvider(SETTINGS.embedding_model)

    parsed_dir = Path(SETTINGS.data_root) / "parsed" / "patents"
    derived_dir = Path(SETTINGS.data_root) / "derived" / "chunks"

    for week_date, url in selected:
        LOGGER.info("Processing week=%s url=%s", week_date, url)
        zip_path = downloader.download_week(week_date, url)
        patents = parse_week_zip(zip_path, parsed_dir)

        all_chunks = []
        for p in patents:
            if not has_cpc_prefix(p, cpc_prefix):
                continue
            pg.upsert_patent(p)
            chunks = build_chunks(p)
            pg.upsert_chunks(chunks)
            os_store.index_chunks(chunks)
            all_chunks.extend(chunks)

        if all_chunks:
            vectors = embedder.embed([c.text for c in all_chunks])
            for c, vec in zip(all_chunks, vectors):
                pg.update_embedding(c.chunk_id, vec)
            write_chunk_jsonl(all_chunks, derived_dir / f"ipg{week_date}.jsonl")
        downloader.mark_processed(week_date)
        LOGGER.info("Completed week=%s chunks=%s", week_date, len(all_chunks))
