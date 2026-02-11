from __future__ import annotations

import hashlib

from patent_mvp.models import EvidenceChunk, PatentDocument
from patent_mvp.text_utils import chunk_paragraph, clean_text


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_id(pub: str, section: str, key: str, text: str) -> str:
    text_hash = _sha(text)
    raw = f"{pub}|{section}|{key}|{text_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_chunks(doc: PatentDocument) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []

    for claim in doc.claims:
        text = clean_text(claim.text)
        text_hash = _sha(text)
        chunks.append(
            EvidenceChunk(
                chunk_id=_chunk_id(doc.publication_number, "CLAIM", claim.claim_num, text),
                publication_number=doc.publication_number,
                section_type="CLAIM",
                claim_num=claim.claim_num,
                is_dependent=claim.is_dependent,
                text=text,
                text_hash=text_hash,
                metadata={"depends_on": claim.depends_on},
            )
        )

    if doc.abstract:
        text = clean_text(doc.abstract)
        chunks.append(
            EvidenceChunk(
                chunk_id=_chunk_id(doc.publication_number, "ABSTRACT", "0", text),
                publication_number=doc.publication_number,
                section_type="ABSTRACT",
                text=text,
                para_id="abstract_0",
                text_hash=_sha(text),
            )
        )

    for section_name, paragraphs in (("SUMMARY", doc.summary_paragraphs), ("DESCRIPTION", doc.description_paragraphs)):
        para_idx = 0
        for para in paragraphs:
            for split_idx, piece in enumerate(chunk_paragraph(para)):
                para_id = f"{section_name.lower()}_{para_idx}_{split_idx}"
                text = clean_text(piece)
                chunks.append(
                    EvidenceChunk(
                        chunk_id=_chunk_id(doc.publication_number, section_name, para_id, text),
                        publication_number=doc.publication_number,
                        section_type=section_name,
                        para_id=para_id,
                        text=text,
                        text_hash=_sha(text),
                    )
                )
            para_idx += 1
    return chunks
