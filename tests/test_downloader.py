import json
from pathlib import Path

from patent_mvp.downloader import PTGRXMLDownloader


def test_parse_search_response_sorts_latest_first() -> None:
    payload = json.loads(Path("tests/fixtures/odp_search_response.json").read_text())
    parsed = PTGRXMLDownloader.parse_search_response(payload)
    assert parsed == [
        ("20240213", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240213.zip"),
        ("20240130", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240130.zip"),
        ("20240102", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240102.zip"),
    ]
