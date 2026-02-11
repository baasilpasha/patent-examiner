from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://bulkdata.uspto.gov/data/patent/grant/redbook/fulltext/"
WEEK_RE = re.compile(r'href="(ipg(\d{8})\.zip)"', re.IGNORECASE)


class PTGRXMLDownloader:
    def __init__(self, data_root: str = "data") -> None:
        self.raw_root = Path(data_root) / "raw" / "ptgrxml"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.raw_root / "processed_weeks.json"

    def _load_state(self) -> set[str]:
        if not self.state_path.exists():
            return set()
        return set(json.loads(self.state_path.read_text()))

    def _save_state(self, weeks: set[str]) -> None:
        self.state_path.write_text(json.dumps(sorted(weeks), indent=2))

    def discover_latest_weeks(self, weeks: int = 12) -> list[tuple[str, str]]:
        year_resp = requests.get(BASE_URL, timeout=30)
        year_resp.raise_for_status()
        years = sorted(set(re.findall(r'href="(\d{4})/"', year_resp.text)))
        results: list[tuple[str, str]] = []
        for y in years[-3:]:
            resp = requests.get(urljoin(BASE_URL, f"{y}/"), timeout=30)
            resp.raise_for_status()
            for fname, date in WEEK_RE.findall(resp.text):
                results.append((date, urljoin(BASE_URL, f"{y}/{fname}")))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:weeks]

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
        with requests.get(url, stream=True, timeout=120, headers=headers) as r:
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
