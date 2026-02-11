from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from patent_mvp.config import SETTINGS

LOGGER = logging.getLogger(__name__)
WEEK_RE = re.compile(r"ipg(\d{8})\.zip", re.IGNORECASE)


class PTGRXMLDownloader:
    def __init__(self, data_root: str = "data", search_url: str | None = None, api_key: str | None = None) -> None:
        self.raw_root = Path(data_root) / "raw" / "ptgrxml"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.raw_root / "processed_weeks.json"
        self.search_url = search_url or SETTINGS.odp_bulk_search_url
        self.api_key = api_key or SETTINGS.odp_api_key

    def _load_state(self) -> set[str]:
        if not self.state_path.exists():
            return set()
        return set(json.loads(self.state_path.read_text()))

    def _save_state(self, weeks: set[str]) -> None:
        self.state_path.write_text(json.dumps(sorted(weeks), indent=2))

    @staticmethod
    def _extract_week_id(record: dict) -> str | None:
        for key in ("fileName", "filename", "name", "downloadFileName"):
            value = str(record.get(key, ""))
            match = WEEK_RE.search(value)
            if match:
                return match.group(1)

        for key in ("fileDataToDate", "fileDataFromDate", "fileDate"):
            value = str(record.get(key, ""))
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 8:
                return digits[:8]
        return None

    @staticmethod
    def _extract_download_url(record: dict) -> str | None:
        for key in ("downloadUrl", "fileDownloadUrl", "url"):
            value = str(record.get(key, "")).strip()
            if value:
                return value
        return None

    @classmethod
    def parse_search_response(cls, payload: dict) -> list[tuple[str, str]]:
        rows = payload.get("results") or payload.get("items") or payload.get("data") or payload.get("response", {}).get("docs") or []
        parsed: list[tuple[str, str]] = []
        for row in rows:
            week_id = cls._extract_week_id(row)
            url = cls._extract_download_url(row)
            if week_id and url:
                parsed.append((week_id, url))

        # Deduplicate by week_id and sort newest first
        dedup: dict[str, str] = {}
        for week_id, url in parsed:
            dedup.setdefault(week_id, url)
        return sorted(dedup.items(), key=lambda x: x[0], reverse=True)

    def discover_latest_weeks(self, weeks: int = 12) -> list[tuple[str, str]]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key

        payload = {
            "dataset": "PTGRXML",
            "page": 0,
            "size": max(weeks * 4, 100),
            "sort": [{"fileDataToDate": "desc"}],
        }
        import requests

        response = requests.post(self.search_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        parsed = self.parse_search_response(response.json())
        selected = parsed[:weeks]
        LOGGER.info("Selected PTGRXML weeks from ODP: %s", [f"{w} -> {u}" for w, u in selected])
        return selected

    def select_weeks(self, weeks: int = 12, since_last: bool = False) -> list[tuple[str, str]]:
        latest = self.discover_latest_weeks(weeks=weeks)
        if not since_last:
            return latest
        processed = self._load_state()
        return [w for w in latest if w[0] not in processed]

    def download_week(self, week_date: str, url: str) -> Path:
        out_dir = self.raw_root / f"ipg{week_date}"
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"ipg{week_date}.zip"
        if zip_path.exists() and zip_path.stat().st_size > 0:
            LOGGER.info("Week %s already downloaded, skipping", week_date)
            return zip_path
        tmp_path = zip_path.with_suffix(".zip.part")
        headers = {}
        if tmp_path.exists():
            headers["Range"] = f"bytes={tmp_path.stat().st_size}-"
            LOGGER.info("Resuming download for week %s from byte %s", week_date, tmp_path.stat().st_size)
        import requests

        with requests.get(url, stream=True, timeout=180, headers=headers) as r:
            r.raise_for_status()
            mode = "ab" if tmp_path.exists() else "wb"
            with tmp_path.open(mode) as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        tmp_path.rename(zip_path)
        return zip_path

    def mark_processed(self, week_date: str) -> None:
        state = self._load_state()
        state.add(week_date)
        self._save_state(state)
