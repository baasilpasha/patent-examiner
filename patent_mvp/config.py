from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql://patent:patent@localhost:5432/patent_mvp")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "patent_chunks")
    data_root: str = os.getenv("DATA_ROOT", "data")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
    odp_bulk_search_url: str = os.getenv("ODP_BULK_SEARCH_URL", "https://api.uspto.gov/api/v1/bulk-data/search")
    odp_dataset_page_url: str = os.getenv(
        "ODP_PTGRXML_DATASET_PAGE_URL",
        "https://data.uspto.gov/datasets/patent-grant-full-text-data-no-images-xml",
    )
    odp_api_key: str | None = os.getenv("ODP_API_KEY")


SETTINGS = Settings()
