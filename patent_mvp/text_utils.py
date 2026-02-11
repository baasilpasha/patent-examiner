from __future__ import annotations

import hashlib
import html
import re
import unicodedata


WS_RE = re.compile(r"\s+")
HYPHEN_WRAP_RE = re.compile(r"(\w)-\s+\n\s*(\w)")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = html.unescape(text)
    text = HYPHEN_WRAP_RE.sub(r"\1\2", text)
    text = text.replace("\x00", " ")
    return WS_RE.sub(" ", text).strip()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(publication_number: str, section_type: str, claim_or_para: str, text: str) -> str:
    payload = f"{publication_number}|{section_type}|{claim_or_para}|{sha256_hex(text)}"
    return sha256_hex(payload)


def split_with_overlap(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks
