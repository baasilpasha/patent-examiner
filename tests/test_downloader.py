import json
from pathlib import Path

from patent_mvp.downloader import PTGRXMLDownloader


def test_parse_search_response_sorts_latest_first_and_dedupes() -> None:
    payload = json.loads(Path("tests/fixtures/odp_search_response.json").read_text())
    parsed = PTGRXMLDownloader.parse_search_response(payload)
    assert parsed == [
        ("20240213", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240213.zip"),
        ("20240130", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240130.zip"),
        ("20240102", "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/ipg20240102.zip"),
    ]


def test_extract_week_id_falls_back_to_file_dates() -> None:
    row = {
        "fileDataToDate": "2024-03-12",
        "downloadUrl": "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/somefile.zip",
    }
    assert PTGRXMLDownloader._extract_week_id(row) == "20240312"
