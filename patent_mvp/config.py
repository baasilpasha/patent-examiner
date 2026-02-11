from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql://patent:patent@localhost:5432/patent_mvp")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "patent_chunks")
    data_root: Path = Path(os.getenv("PATENT_MVP_DATA_ROOT", "data"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
    batch_size: int = int(os.getenv("EMBED_BATCH_SIZE", "64"))

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "raw" / "ptgrxml"

    @property
    def parsed_dir(self) -> Path:
        return self.data_root / "parsed" / "patents"

    @property
    def derived_dir(self) -> Path:
        return self.data_root / "derived" / "chunks"
