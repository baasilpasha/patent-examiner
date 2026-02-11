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


def test_parse_dataset_page_links_sorts_latest_first_and_dedupes() -> None:
    html = Path("tests/fixtures/odp_dataset_page.html").read_text()
    parsed = PTGRXMLDownloader.parse_dataset_page_links(
        html,
        "https://data.uspto.gov/datasets/patent-grant-full-text-data-no-images-xml",
    )
    assert parsed == [
        ("20240213", "https://data.uspto.gov/downloads/ipg20240213.zip"),
        ("20240130", "https://data.uspto.gov/downloads/ipg20240130.zip"),
        ("20240102", "https://cdn.example.org/ptgrxml/ipg20240102.zip"),
    ]


def test_extract_week_id_falls_back_to_file_dates() -> None:
    row = {
        "fileDataToDate": "2024-03-12",
        "downloadUrl": "https://api.uspto.gov/api/v1/bulk-data/download/PTGRXML/somefile.zip",
    }
    assert PTGRXMLDownloader._extract_week_id(row) == "20240312"


def test_select_weeks_skips_processed_even_without_since_last(tmp_path) -> None:
    downloader = PTGRXMLDownloader(data_root=str(tmp_path))
    downloader._save_state({"20240213"})
    downloader.discover_latest_weeks = lambda weeks=12: [
        ("20240213", "https://example.org/ipg20240213.zip"),
        ("20240130", "https://example.org/ipg20240130.zip"),
    ]

    selected = downloader.select_weeks(weeks=2, since_last=False)

    assert selected == [("20240130", "https://example.org/ipg20240130.zip")]
