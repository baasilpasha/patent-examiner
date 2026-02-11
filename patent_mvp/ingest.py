from __future__ import annotations

from dataclasses import asdict
import json
import logging
from pathlib import Path
import zipfile

from patent_mvp.chunking import build_chunks
from patent_mvp.config import Settings
from patent_mvp.db import PostgresStore
from patent_mvp.downloader import PTGRXMLDownloader, WeekBatch
from patent_mvp.embeddings import SentenceTransformerProvider
from patent_mvp.parser import is_target_cpc, parse_patent_xml
from patent_mvp.search_index import OpenSearchStore

logger = logging.getLogger(__name__)


def _extract_zip(zip_path: Path) -> list[Path]:
    xml_files: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                target = zip_path.parent / Path(name).name
                if not target.exists():
                    zf.extract(name, zip_path.parent)
                    extracted = zip_path.parent / name
                    if extracted != target:
                        extracted.rename(target)
                xml_files.append(target)
    return xml_files


def select_batches(downloader: PTGRXMLDownloader, weeks: int, since_last: str | None) -> list[WeekBatch]:
    available = downloader.list_available_weeks()
    if since_last:
        selected = [w for w in available if w.week_id > since_last]
    else:
        selected = available[-weeks:]
    return selected


def run_ingest(settings: Settings, weeks: int, cpc_prefix: str, since_last: bool = False) -> None:
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.parsed_dir.mkdir(parents=True, exist_ok=True)
    settings.derived_dir.mkdir(parents=True, exist_ok=True)

    db = PostgresStore(settings.postgres_dsn)
    index = OpenSearchStore(settings.opensearch_url, settings.opensearch_index)
    index.ensure_index(Path("opensearch/chunks_mapping.json"))
    downloader = PTGRXMLDownloader(settings.raw_dir)

    last_week = db.get_last_week("ptgrxml") if since_last else None
    batches = select_batches(downloader, weeks=weeks, since_last=last_week)
    if not batches:
        logger.info("No new batches found.")
        return

    for batch in batches:
        logger.info("Processing %s", batch.week_id)
        zip_path = downloader.download_week(batch)
        xml_files = _extract_zip(zip_path)
        week_chunks: list[dict] = []
        for xml in xml_files:
            docs = parse_patent_xml(xml)
            for doc in docs:
                if not is_target_cpc(doc.cpc_codes, cpc_prefix):
                    continue
                db.upsert_patent(doc)
                parsed_path = settings.parsed_dir / f"{doc.publication_number}.json"
                parsed_path.write_text(json.dumps(asdict(doc)))
                chunks = build_chunks(doc)
                db.upsert_chunks(chunks)
                index.upsert_chunks(chunks)
                week_chunks.extend(asdict(c) for c in chunks)

        out_jsonl = settings.derived_dir / f"ipg{batch.week_id}.jsonl"
        with out_jsonl.open("w") as fh:
            for row in week_chunks:
                fh.write(json.dumps(row) + "\n")
        db.set_last_week("ptgrxml", batch.week_id)

    embedder = SentenceTransformerProvider(
        model_name=settings.embedding_model,
        cache_path=settings.data_root / "derived" / "embedding_cache.json",
        batch_size=settings.batch_size,
    )
    while True:
        missing = db.fetch_chunks_missing_embeddings(limit=500)
        if not missing:
            break
        vectors = embedder.embed([m[1] for m in missing])
        db.update_embeddings([(missing[idx][0], vec) for idx, vec in enumerate(vectors)])
        logger.info("Embedded %s chunks", len(missing))
