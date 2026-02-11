from __future__ import annotations

import json
from pathlib import Path

from patent_mvp.models import EvidenceChunk, PatentRecord
from patent_mvp.text_utils import make_chunk_id, normalize_text, sha256_hex, split_with_overlap


def has_cpc_prefix(patent: PatentRecord, prefix: str = "G06F") -> bool:
    up = prefix.upper()
    return any(c.upper().startswith(up) for c in patent.cpc_codes)


def _chunk_from_text(p: PatentRecord, section: str, text: str, ident: str) -> EvidenceChunk:
    clean = normalize_text(text)
    return EvidenceChunk(
        chunk_id=make_chunk_id(p.publication_number, section, ident, clean),
        publication_number=p.publication_number,
        section_type=section,
        text=clean,
        para_id=ident if section in {"SUMMARY", "DESCRIPTION"} else None,
        metadata={"text_hash": sha256_hex(clean)},
    )


def build_chunks(patent: PatentRecord, max_chars: int = 1200, overlap: int = 150) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for c in patent.claims:
        claim_num = str(c.get("claim_num") or "unknown")
        text = normalize_text(str(c["text"]))
        chunks.append(
            EvidenceChunk(
                chunk_id=make_chunk_id(patent.publication_number, "CLAIM", claim_num, text),
                publication_number=patent.publication_number,
                section_type="CLAIM",
                text=text,
                claim_num=claim_num,
                is_independent=bool(c.get("is_independent", True)),
                metadata={"text_hash": sha256_hex(text)},
            )
        )

    if patent.abstract:
        chunks.append(_chunk_from_text(patent, "ABSTRACT", patent.abstract, "abstract"))

    for idx, para in enumerate(patent.summary_paragraphs, start=1):
        for part_i, piece in enumerate(split_with_overlap(para, max_chars=max_chars, overlap=overlap), start=1):
            chunks.append(_chunk_from_text(patent, "SUMMARY", piece, f"s{idx}_{part_i}"))

    for idx, para in enumerate(patent.description_paragraphs, start=1):
        for part_i, piece in enumerate(split_with_overlap(para, max_chars=max_chars, overlap=overlap), start=1):
            chunks.append(_chunk_from_text(patent, "DESCRIPTION", piece, f"d{idx}_{part_i}"))

    return chunks


def write_chunk_jsonl(chunks: list[EvidenceChunk], out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
