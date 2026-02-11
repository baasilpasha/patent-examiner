from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Claim:
    claim_num: str
    text: str
    is_dependent: bool
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PatentDocument:
    publication_number: str
    grant_date: str
    title: str
    abstract: str
    summary_paragraphs: list[str]
    description_paragraphs: list[str]
    claims: list[Claim]
    cpc_codes: list[str]
    citations: list[str]
    raw: dict[str, Any]


@dataclass
class EvidenceChunk:
    chunk_id: str
    publication_number: str
    section_type: str
    text: str
    text_hash: str
    claim_num: str | None = None
    para_id: str | None = None
    is_dependent: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
