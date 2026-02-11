from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import httpx

PTGRXML_BASE = "https://bulkdata.uspto.gov/data/patent/grant/redbook/fulltext/"
_WEEK_RE = re.compile(r"href=\"(ipg(\d{8})\.zip)\"")


@dataclass(frozen=True)
class WeekBatch:
    week_id: str
    file_name: str
    url: str


class PTGRXMLDownloader:
    def __init__(self, raw_root: Path, timeout_s: int = 60) -> None:
        self.raw_root = raw_root
        self.client = httpx.Client(timeout=timeout_s)

    def list_available_weeks(self) -> list[WeekBatch]:
        response = self.client.get(PTGRXML_BASE)
        response.raise_for_status()
        matches = _WEEK_RE.findall(response.text)
        weeks = [WeekBatch(week_id=week, file_name=file_name, url=f"{PTGRXML_BASE}{file_name}") for file_name, week in matches]
        weeks.sort(key=lambda w: w.week_id)
        return weeks

    def newest_weeks(self, n: int) -> list[WeekBatch]:
        weeks = self.list_available_weeks()
        return weeks[-n:]

    def download_week(self, batch: WeekBatch) -> Path:
        target_dir = self.raw_root / f"ipg{batch.week_id}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_zip = target_dir / batch.file_name
        if target_zip.exists() and target_zip.stat().st_size > 0:
            return target_zip

        tmp_file = target_zip.with_suffix(".part")
        headers = {}
        if tmp_file.exists():
            headers["Range"] = f"bytes={tmp_file.stat().st_size}-"

        with self.client.stream("GET", batch.url, headers=headers) as response:
            if response.status_code not in (200, 206):
                response.raise_for_status()
            mode = "ab" if response.status_code == 206 and tmp_file.exists() else "wb"
            with tmp_file.open(mode) as fh:
                for chunk in response.iter_bytes(1024 * 1024):
                    fh.write(chunk)
        tmp_file.replace(target_zip)
        return target_zip
