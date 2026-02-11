from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatentRecord:
    publication_number: str
    grant_date: str | None
    title: str
    abstract: str
    summary_paragraphs: list[str]
    description_paragraphs: list[str]
    claims: list[dict[str, Any]]
    cpc_codes: list[str]
    citations: list[str]
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceChunk:
    chunk_id: str
    publication_number: str
    section_type: str
    text: str
    claim_num: str | None = None
    para_id: str | None = None
    is_independent: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
