from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("lxml")

import patent_mvp.ingest as ingest_mod


class _FakeDownloader:
    def __init__(self, data_root: str) -> None:
        self.data_root = data_root
        self.marked: list[str] = []

    def select_weeks(self, weeks: int, since_last: bool) -> list[tuple[str, str]]:
        return [("20250107", "https://example.local/ipg20250107.zip")]

    def download_week(self, week_date: str, url: str) -> Path:
        return Path(self.data_root) / "raw" / "ptgrxml" / f"ipg{week_date}" / f"ipg{week_date}.zip"

    def mark_processed(self, week_date: str) -> None:
        self.marked.append(week_date)


class _FakePostgresStore:
    def __init__(self, dsn: str) -> None:
        self.patents: list[str] = []
        self.chunk_ids: list[str] = []

    def upsert_patent(self, patent) -> None:
        self.patents.append(patent.publication_number)

    def upsert_chunks(self, chunks) -> None:
        self.chunk_ids.extend([c.chunk_id for c in chunks])

    def update_embedding(self, chunk_id: str, embedding: list[float]) -> None:
        assert len(embedding) == 768


class _FakeOpenSearchStore:
    def __init__(self, base_url: str, index_name: str) -> None:
        self.indexed: list[str] = []

    def ensure_index(self) -> None:
        return

    def index_chunks(self, chunks) -> None:
        self.indexed.extend([c.chunk_id for c in chunks])


class _FakeEmbedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]


def test_run_ingest_smoke_with_fixture_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    week = "20250107"
    zip_dir = tmp_path / "raw" / "ptgrxml" / f"ipg{week}"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"ipg{week}.zip"
    fixture_xml = Path("tests/fixtures/sample_patent.xml")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ipg.xml", fixture_xml.read_text())

    monkeypatch.setattr(ingest_mod, "SETTINGS", SimpleNamespace(
        data_root=str(tmp_path),
        postgres_dsn="postgresql://unused",
        opensearch_url="http://unused",
        opensearch_index="unused",
        embedding_model="BAAI/bge-base-en-v1.5",
    ))
    monkeypatch.setattr(ingest_mod, "PTGRXMLDownloader", _FakeDownloader)
    monkeypatch.setattr(ingest_mod, "PostgresStore", _FakePostgresStore)
    monkeypatch.setattr(ingest_mod, "OpenSearchStore", _FakeOpenSearchStore)
    monkeypatch.setattr(ingest_mod, "SentenceTransformerProvider", _FakeEmbedder)

    ingest_mod.run_ingest(weeks=1, cpc_prefix="G06F", since_last=False)

    parsed_file = tmp_path / "parsed" / "patents" / "US1234567B2.json"
    chunk_file = tmp_path / "derived" / "chunks" / f"ipg{week}.jsonl"

    assert parsed_file.exists()
    assert chunk_file.exists()
    lines = [json.loads(line) for line in chunk_file.read_text().splitlines()]
    assert len(lines) >= 4
    assert any(line["section_type"] == "CLAIM" for line in lines)
